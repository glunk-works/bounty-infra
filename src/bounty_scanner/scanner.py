import os
import json
import logging
import subprocess
import datetime
import sys
import boto3
import tempfile
from typing import List, Optional
from dataclasses import dataclass
from contextlib import contextmanager
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants for token management
MAX_FINDINGS_FOR_LLM = 50
TARGET_SEVERITIES = {"medium", "high", "critical"}
SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
    "unknown": 0,
}


@dataclass
class ReconArtifacts:
    findings: List[dict]
    subs_file: str
    live_file: str
    nuclei_file: str


class Finding(BaseModel):
    title: str = Field(..., description="The name of the vulnerability.")
    severity: str = Field(..., description="Severity level.")
    target: str = Field(..., description="The affected URL or host.")
    description: str = Field(..., description="Brief summary of the issue.")
    remediation: str = Field(..., description="Actionable fix steps.")


class TriageReport(BaseModel):
    top_findings: List[Finding] = Field(..., description="Top 3 critical findings.")
    summary: str = Field(..., description="Executive summary of risks.")


@contextmanager
def run_recon_pipeline(domain: str, timeout: int = 1800):
    """Runs recon pipeline using disk-backed I/O. Yields paths safely as a context manager."""
    findings = []

    # Create temporary files for standard output routing
    subs_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    live_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    nuclei_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl")

    # Close them so subprocesses can open and write to them safely
    subs_file.close()
    live_file.close()
    nuclei_file.close()

    artifacts = ReconArtifacts(
        findings=findings,
        subs_file=subs_file.name,
        live_file=live_file.name,
        nuclei_file=nuclei_file.name,
    )

    try:
        logger.info(f"Running subfinder on {domain}...")
        with open(artifacts.subs_file, "w") as f_out:
            subprocess.run(
                ["subfinder", "-d", domain, "-silent"],
                stdout=f_out,
                check=True,
                timeout=timeout,
            )

        # Check if subfinder found anything before continuing
        if os.path.getsize(artifacts.subs_file) > 0:
            logger.info("Running httpx for liveness check...")
            with (
                open(artifacts.subs_file, "r") as f_in,
                open(artifacts.live_file, "w") as f_out,
            ):
                subprocess.run(
                    ["httpx", "-silent"],
                    stdin=f_in,
                    stdout=f_out,
                    check=True,
                    timeout=timeout,
                )

            if os.path.getsize(artifacts.live_file) > 0:
                logger.info("Running nuclei scanning...")
                with (
                    open(artifacts.live_file, "r") as f_in,
                    open(artifacts.nuclei_file, "w") as f_out,
                ):
                    subprocess.run(
                        ["nuclei", "-jsonl", "-silent"],
                        stdin=f_in,
                        stdout=f_out,
                        check=True,
                        timeout=timeout,
                    )

                # Read the nuclei output line-by-line (highly memory efficient)
                with open(artifacts.nuclei_file, "r") as results:
                    for line in results:
                        if line.strip():
                            try:
                                artifacts.findings.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        else:
            logger.warning("No subdomains found.")

        yield artifacts

    except subprocess.TimeoutExpired as e:
        logger.error(f"Pipeline tool timed out after {e.timeout} seconds: {e.cmd}")
        yield artifacts  # Yield whatever was collected before the timeout
    except subprocess.CalledProcessError as e:
        logger.error(f"Pipeline tool failed during execution: {e}")
        yield artifacts  # Yield whatever was collected before the crash

    finally:
        # Cleanup ephemeral disk space once the context manager exits
        for path in [artifacts.subs_file, artifacts.live_file, artifacts.nuclei_file]:
            if os.path.exists(path):
                os.unlink(path)


def triage_findings(findings: List[dict]) -> Optional[TriageReport]:
    """Uses Gemini to triage findings with strict token/context management."""
    if not findings:
        return None

    # 1. Filter out info/low level noise to save tokens
    actionable_findings = [
        f
        for f in findings
        if f.get("info", {}).get("severity", "unknown").lower() in TARGET_SEVERITIES
    ]

    if not actionable_findings:
        logger.info("No actionable (Medium+) findings to triage.")
        return None

    # 2. Sort by severity so if we hit the limit, we drop the lowest risks
    actionable_findings.sort(
        key=lambda x: SEVERITY_WEIGHT.get(
            x.get("info", {}).get("severity", "unknown").lower(), 0
        ),
        reverse=True,
    )

    # 3. Truncate to the maximum allowed items and prepare LLM warning if needed
    total_actionable = len(actionable_findings)
    truncated_findings = actionable_findings[:MAX_FINDINGS_FOR_LLM]

    truncation_warning = ""
    if total_actionable > MAX_FINDINGS_FOR_LLM:
        logger.warning(
            f"Truncated LLM payload from {total_actionable} down to {MAX_FINDINGS_FOR_LLM} items."
        )
        truncation_warning = (
            f" IMPORTANT NOTE: The scan found {total_actionable} actionable findings, but this list "
            f"has been truncated to the top {MAX_FINDINGS_FOR_LLM} most severe issues due to LLM context limits. "
            "You MUST mention this truncation explicitly in your summary so the team knows there is a backlog of issues."
        )

    # 4. Prune the JSON (Strip massive HTTP request/response payloads)
    lightweight_findings = []
    for f in truncated_findings:
        info = f.get("info", {})
        lightweight_findings.append(
            {
                "id": f.get("template-id"),
                "severity": info.get("severity"),
                "name": info.get("name"),
                "target": f.get("matched-at"),
                "description": info.get("description", "No description provided."),
            }
        )

    client = genai.Client()
    prompt = (
        f"Analyze the following {len(lightweight_findings)} JSON findings from a vulnerability scan. "
        "Identify and extract the top 3 most critical findings that pose "
        "the highest immediate operational risk. Provide a concise summary."
        f"{truncation_warning}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, json.dumps(lightweight_findings)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TriageReport,
            ),
        )
        return TriageReport.model_validate_json(response.text)
    except Exception as e:
        logger.error(f"LLM triage failed: {e}")
        return None


def upload_to_s3(
    domain: str, report: Optional[TriageReport], artifacts: ReconArtifacts
):
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not bucket_name:
        logger.warning("No S3_BUCKET_NAME env var found. Skipping S3 upload.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    s3 = boto3.client("s3")

    # Define S3 prefix structures
    base_prefix = f"{domain}/{timestamp}"
    artifacts_prefix = f"{base_prefix}/artifacts"

    try:
        logger.info(f"Uploading artifacts to s3://{bucket_name}/{base_prefix}/")

        # Upload the processed JSON reports
        if report:
            s3.put_object(
                Bucket=bucket_name,
                Key=f"{base_prefix}/triage_report.json",
                Body=report.model_dump_json(indent=2),
            )
        s3.put_object(
            Bucket=bucket_name,
            Key=f"{base_prefix}/raw_findings.json",
            Body=json.dumps(artifacts.findings, indent=2),
        )

        # Upload the raw disk files into the artifacts subfolder
        if os.path.getsize(artifacts.subs_file) > 0:
            s3.upload_file(
                artifacts.subs_file, bucket_name, f"{artifacts_prefix}/subdomains.txt"
            )

        if os.path.getsize(artifacts.live_file) > 0:
            s3.upload_file(
                artifacts.live_file, bucket_name, f"{artifacts_prefix}/live_hosts.txt"
            )

        if os.path.getsize(artifacts.nuclei_file) > 0:
            s3.upload_file(
                artifacts.nuclei_file,
                bucket_name,
                f"{artifacts_prefix}/nuclei_output.jsonl",
            )

        logger.info("Upload complete.")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m bounty_scanner.scanner <domain>")
        sys.exit(1)

    target_domain = sys.argv[1]

    # Context manager ensures files are deleted after block exits
    with run_recon_pipeline(target_domain) as artifacts:
        logger.info(f"Found {len(artifacts.findings)} raw findings. Triaging...")
        report = triage_findings(artifacts.findings)

        if report:
            print("\n=== EXECUTIVE SUMMARY ===")
            print(report.summary)
            print("\n=== TOP 3 CRITICAL FINDINGS ===")
            for idx, finding in enumerate(report.top_findings, 1):
                print(f"\n{idx}. {finding.title} [{finding.severity}]")
                print(f"   Target: {finding.target}")

        # Upload AI data and raw disk artifacts
        upload_to_s3(target_domain, report, artifacts)


if __name__ == "__main__":
    main()
