import os
import json
import logging
import subprocess
import datetime
import boto3
from typing import List, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class Finding(BaseModel):
    title: str = Field(..., description="The name of the vulnerability.")
    severity: str = Field(..., description="Severity level.")
    target: str = Field(..., description="The affected URL or host.")
    description: str = Field(..., description="Brief summary of the issue.")
    remediation: str = Field(..., description="Actionable fix steps.")

class TriageReport(BaseModel):
    top_findings: List[Finding] = Field(..., description="Top 3 critical findings.")
    summary: str = Field(..., description="Executive summary of risks.")

def run_recon_pipeline(domain: str) -> List[dict]:
    """Runs subfinder -> httpx -> nuclei."""
    try:
        logger.info(f"Running subfinder on {domain}...")
        subfinder = subprocess.run(
            ["subfinder", "-d", domain, "-silent"],
            capture_output=True, text=True, check=True,
        )
        subdomains = subfinder.stdout.strip()
        if not subdomains:
            logger.warning("No subdomains found.")
            return []

        logger.info("Running httpx for liveness check...")
        httpx = subprocess.run(
            ["httpx", "-silent"],
            input=subdomains,
            capture_output=True, text=True, check=True,
        )
        live_hosts = httpx.stdout.strip()
        if not live_hosts:
            return []

        logger.info("Running nuclei scanning...")
        nuclei = subprocess.run(
            ["nuclei", "-jsonl", "-silent"],
            input=live_hosts,
            capture_output=True, text=True, check=True,
        )

        findings = []
        for line in nuclei.stdout.splitlines():
            if line.strip():
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return findings

    except subprocess.CalledProcessError as e:
        logger.error(f"Pipeline tool failed: {e.stderr}")
        return []

def triage_findings(findings: List[dict]) -> Optional[TriageReport]:
    """Uses Gemini 1.5 Flash to triage findings."""
    if not findings:
        return None

    lightweight_findings = [
        {
            "template-id": f.get("template-id"),
            "info": f.get("info", {}),
            "matched-at": f.get("matched-at"),
            "extracted-results": f.get("extracted-results"),
        } for f in findings
    ]

    client = genai.Client() # Assumes GEMINI_API_KEY is in env
    prompt = (
        "Analyze the following JSON findings from a vulnerability scan. "
        "Identify and extract the top 3 most critical findings that pose "
        "the highest immediate operational risk. Provide a concise summary."
    )

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
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

def upload_to_s3(domain: str, report: TriageReport, raw_findings: List[dict]):
    """Uploads the results to the central findings bucket."""
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not bucket_name:
        logger.warning("No S3_BUCKET_NAME env var found. Skipping S3 upload.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    s3 = boto3.client('s3')
    
    report_key = f"{domain}/{timestamp}_triage_report.json"
    raw_key = f"{domain}/{timestamp}_raw_findings.json"

    try:
        logger.info(f"Uploading artifacts to s3://{bucket_name}/{domain}/")
        s3.put_object(Bucket=bucket_name, Key=report_key, Body=report.model_dump_json(indent=2))
        s3.put_object(Bucket=bucket_name, Key=raw_key, Body=json.dumps(raw_findings, indent=2))
        logger.info("Upload complete.")
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scanner.py <domain>")
        sys.exit(1)

    target_domain = sys.argv[1]
    raw_findings = run_recon_pipeline(target_domain)
    
    logger.info(f"Found {len(raw_findings)} raw findings. Triaging...")
    report = triage_findings(raw_findings)

    if report:
        print("\n=== EXECUTIVE SUMMARY ===")
        print(report.summary)
        print("\n=== TOP 3 CRITICAL FINDINGS ===")
        for idx, finding in enumerate(report.top_findings, 1):
            print(f"\n{idx}. {finding.title} [{finding.severity}]")
            print(f"   Target: {finding.target}")
        
        # Save to the global-bootstrap bucket
        upload_to_s3(target_domain, report, raw_findings)
    else:
        logger.info("No actionable findings identified.")

if __name__ == "__main__":
    main()
