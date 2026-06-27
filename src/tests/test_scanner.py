import os
import json
import subprocess
import pytest
from unittest.mock import MagicMock, mock_open, call

from bounty_scanner.scanner import (
    run_recon_pipeline,
    triage_findings,
    upload_to_s3,
    main,
    Finding,
    TriageReport,
    ReconArtifacts,
    MAX_FINDINGS_FOR_LLM
)

# ==========================================
# TEST FIXTURES
# ==========================================

@pytest.fixture
def mock_raw_findings():
    return [
        {
            "template-id": "cve-2021-44228",
            "info": {"name": "Log4j RCE", "severity": "critical"},
            "matched-at": "https://example.com/api",
            "extracted-results": []
        },
        {
            "template-id": "tech-detect",
            "info": {"name": "Nginx Detected", "severity": "info"},
            "matched-at": "https://example.com",
            "extracted-results": ["nginx/1.18.0"]
        }
    ]

@pytest.fixture
def mock_artifacts(mock_raw_findings):
    return ReconArtifacts(
        findings=mock_raw_findings,
        subs_file="/tmp/subs.txt",
        live_file="/tmp/live.txt",
        nuclei_file="/tmp/nuclei.jsonl"
    )

@pytest.fixture
def mock_triage_report():
    return TriageReport(
        summary="A critical Log4j vulnerability was found.",
        top_findings=[
            Finding(
                title="Log4j RCE",
                severity="critical",
                target="https://example.com/api",
                description="Remote code execution via Log4j.",
                remediation="Update Log4j to 2.17.1 or higher."
            )
        ]
    )

# ==========================================
# TESTS FOR: run_recon_pipeline
# ==========================================

def test_run_recon_pipeline_success(mocker, mock_raw_findings):
    """Test successful execution with disk-backed I/O."""
    mocker.patch("subprocess.run")
    mocker.patch("os.path.getsize", return_value=100) # Mock files having content
    
    # Mock reading the nuclei JSONL output
    mocked_file_data = "\n".join([json.dumps(f) for f in mock_raw_findings])
    mocker.patch("builtins.open", mock_open(read_data=mocked_file_data))

    with run_recon_pipeline("example.com") as artifacts:
        assert len(artifacts.findings) == 2
        assert artifacts.findings[0]["template-id"] == "cve-2021-44228"

def test_run_recon_pipeline_no_subdomains(mocker):
    """Test pipeline stops early if subfinder finds nothing (0 bytes)."""
    mock_run = mocker.patch("subprocess.run")
    mocker.patch("os.path.getsize", return_value=0)

    # Test passing a custom timeout overrides the default
    with run_recon_pipeline("example.com", timeout=300) as artifacts:
        assert artifacts.findings == []
        assert mock_run.call_count == 1  # Only subfinder runs
        
        # Validate that the timeout param was successfully passed down to subprocess
        mock_run.assert_called_with(["subfinder", "-d", "example.com", "-silent"], stdout=mocker.ANY, check=True, timeout=300)

def test_run_recon_pipeline_subprocess_error(mocker):
    """Test gracefully yielding current state on binary crash."""
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd"))
    
    with run_recon_pipeline("example.com") as artifacts:
        assert artifacts.findings == []

def test_run_recon_pipeline_subprocess_timeout(mocker):
    """Test gracefully yielding current state when a binary times out."""
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 1800))
    
    with run_recon_pipeline("example.com") as artifacts:
        assert artifacts.findings == []

# ==========================================
# TESTS FOR: triage_findings
# ==========================================

def test_triage_findings_success(mocker, mock_raw_findings, mock_triage_report):
    """Test LLM parsing of actionable findings."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=mock_triage_report.model_dump_json())
    mocker.patch("bounty_scanner.scanner.genai.Client", return_value=mock_client)

    report = triage_findings(mock_raw_findings)

    assert report is not None
    assert report.summary == "A critical Log4j vulnerability was found."
    assert len(report.top_findings) == 1

def test_triage_findings_truncation_warning(mocker, mock_triage_report):
    """Test that finding lists > MAX are truncated and AI is warned."""
    many_findings = [
        {"template-id": f"cve-{i}", "info": {"severity": "critical"}}
        for i in range(MAX_FINDINGS_FOR_LLM + 5)
    ]
    
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=mock_triage_report.model_dump_json())
    mocker.patch("bounty_scanner.scanner.genai.Client", return_value=mock_client)
    mock_logger = mocker.patch("bounty_scanner.scanner.logger.warning")

    report = triage_findings(many_findings)

    assert report is not None
    mock_logger.assert_called_with(f"Truncated LLM payload from {MAX_FINDINGS_FOR_LLM + 5} down to {MAX_FINDINGS_FOR_LLM} items.")
    
    # Assert the prompt injection happened
    prompt_used = mock_client.models.generate_content.call_args[1]["contents"][0]
    assert "IMPORTANT NOTE:" in prompt_used

def test_triage_findings_only_low_info(mocker):
    """Test that triage aborts if only Low/Info findings exist."""
    noise_findings = [
        {"template-id": "tech-detect", "info": {"severity": "info"}},
        {"template-id": "low-vuln", "info": {"severity": "low"}}
    ]
    report = triage_findings(noise_findings)
    assert report is None

def test_triage_findings_empty_input():
    assert triage_findings([]) is None

# ==========================================
# TESTS FOR: upload_to_s3
# ==========================================

def test_upload_to_s3_success(mocker, mock_triage_report, mock_artifacts):
    """Test S3 artifact upload paths and methods."""
    mocker.patch.dict(os.environ, {"S3_BUCKET_NAME": "test-bucket"})
    mock_s3 = MagicMock()
    mocker.patch("bounty_scanner.scanner.boto3.client", return_value=mock_s3)
    mocker.patch("os.path.getsize", return_value=10) # Mock files as having content

    upload_to_s3("example.com", mock_triage_report, mock_artifacts)

    # Put object (Report & Raw JSON)
    assert mock_s3.put_object.call_count == 2
    
    # Upload file (3 Text/JSONL Artifacts)
    assert mock_s3.upload_file.call_count == 3
    
    # Verify artifact structural paths
    calls = mock_s3.upload_file.call_args_list
    assert calls[0] == call("/tmp/subs.txt", "test-bucket", mocker.ANY)
    assert calls[1] == call("/tmp/live.txt", "test-bucket", mocker.ANY)
    assert calls[2] == call("/tmp/nuclei.jsonl", "test-bucket", mocker.ANY)

def test_upload_to_s3_missing_bucket(mocker, mock_triage_report, mock_artifacts):
    if "S3_BUCKET_NAME" in os.environ:
        del os.environ["S3_BUCKET_NAME"]
        
    mock_s3 = mocker.patch("bounty_scanner.scanner.boto3.client")
    upload_to_s3("example.com", mock_triage_report, mock_artifacts)
    mock_s3.assert_not_called()

# ==========================================
# TESTS FOR: main orchestration
# ==========================================

def test_main_success(mocker, mock_triage_report, mock_artifacts):
    """Test end-to-end execution of main orchestrator."""
    mocker.patch("sys.argv", ["scanner.py", "example.com"])
    
    # Mock context manager for recon
    mock_recon_cm = MagicMock()
    mock_recon_cm.__enter__.return_value = mock_artifacts
    mocker.patch("bounty_scanner.scanner.run_recon_pipeline", return_value=mock_recon_cm)
    
    mock_triage = mocker.patch("bounty_scanner.scanner.triage_findings", return_value=mock_triage_report)
    mock_upload = mocker.patch("bounty_scanner.scanner.upload_to_s3")

    main()

    mock_triage.assert_called_once_with(mock_artifacts.findings)
    mock_upload.assert_called_once_with("example.com", mock_triage_report, mock_artifacts)

def test_main_missing_args(mocker):
    mocker.patch("sys.argv", ["scanner.py"])
    
    with pytest.raises(SystemExit) as excinfo:
        main()
        
    assert excinfo.value.code == 1
