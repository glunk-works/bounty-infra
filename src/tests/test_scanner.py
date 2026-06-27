import os
import json
import subprocess
import pytest
from unittest.mock import MagicMock

# Import the module components to test
from bounty_scanner.scanner import (
    run_recon_pipeline,
    triage_findings,
    upload_to_s3,
    main,
    Finding,
    TriageReport
)

# ==========================================
# TEST FIXTURES
# ==========================================

@pytest.fixture
def mock_raw_findings():
    """Provides a sample list of raw Nuclei findings."""
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
def mock_triage_report():
    """Provides a sample TriageReport object."""
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
    """Test successful execution of the recon pipeline (subfinder -> httpx -> nuclei)."""
    # Mock the 3 sequential subprocess calls
    mock_subfinder = MagicMock(stdout="sub.example.com\n")
    mock_httpx = MagicMock(stdout="https://sub.example.com\n")
    mock_nuclei = MagicMock(stdout=json.dumps(mock_raw_findings[0]) + "\n" + json.dumps(mock_raw_findings[1]) + "\n")
    
    mocker.patch(
        "bounty_scanner.scanner.subprocess.run",
        side_effect=[mock_subfinder, mock_httpx, mock_nuclei]
    )

    results = run_recon_pipeline("example.com")
    
    assert len(results) == 2
    assert results[0]["template-id"] == "cve-2021-44228"

def test_run_recon_pipeline_no_subdomains(mocker):
    """Test pipeline stops early if subfinder finds nothing."""
    mock_subfinder = MagicMock(stdout="")
    mock_run = mocker.patch("bounty_scanner.scanner.subprocess.run", return_value=mock_subfinder)

    results = run_recon_pipeline("example.com")
    
    assert results == []
    assert mock_run.call_count == 1  # Should not call httpx or nuclei

def test_run_recon_pipeline_subprocess_error(mocker):
    """Test pipeline gracefully handles a crash in the underlying binaries."""
    mocker.patch(
        "bounty_scanner.scanner.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "subfinder", stderr="Crash")
    )

    results = run_recon_pipeline("example.com")
    assert results == []

# ==========================================
# TESTS FOR: triage_findings
# ==========================================

def test_triage_findings_success(mocker, mock_raw_findings, mock_triage_report):
    """Test that the LLM successfully parses findings into a TriageReport."""
    # Mock the Gemini client and its response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_triage_report.model_dump_json()
    mock_client.models.generate_content.return_value = mock_response
    
    mocker.patch("bounty_scanner.scanner.genai.Client", return_value=mock_client)

    report = triage_findings(mock_raw_findings)

    assert report is not None
    assert report.summary == "A critical Log4j vulnerability was found."
    assert len(report.top_findings) == 1
    assert report.top_findings[0].severity == "critical"

def test_triage_findings_empty_input():
    """Test triaging handles empty finding lists immediately."""
    assert triage_findings([]) is None

def test_triage_findings_llm_exception(mocker, mock_raw_findings):
    """Test triaging handles Gemini API failures gracefully."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API Rate Limit")
    mocker.patch("bounty_scanner.scanner.genai.Client", return_value=mock_client)

    report = triage_findings(mock_raw_findings)
    assert report is None

# ==========================================
# TESTS FOR: upload_to_s3
# ==========================================

def test_upload_to_s3_success(mocker, mock_triage_report, mock_raw_findings):
    """Test that S3 upload fires twice (report and raw) when configured."""
    mocker.patch.dict(os.environ, {"S3_BUCKET_NAME": "test-bucket"})
    mock_s3 = MagicMock()
    mocker.patch("bounty_scanner.scanner.boto3.client", return_value=mock_s3)

    upload_to_s3("example.com", mock_triage_report, mock_raw_findings)

    assert mock_s3.put_object.call_count == 2
    
    # Verify the first call was for the triage report
    call_args = mock_s3.put_object.call_args_list[0][1]
    assert call_args["Bucket"] == "test-bucket"
    assert "_triage_report.json" in call_args["Key"]

def test_upload_to_s3_missing_bucket(mocker, mock_triage_report, mock_raw_findings):
    """Test that S3 upload is safely skipped if the env var is missing."""
    if "S3_BUCKET_NAME" in os.environ:
        del os.environ["S3_BUCKET_NAME"]
        
    mock_s3 = mocker.patch("bounty_scanner.scanner.boto3.client")

    upload_to_s3("example.com", mock_triage_report, mock_raw_findings)
    mock_s3.assert_not_called()

# ==========================================
# TESTS FOR: main orchestration
# ==========================================

def test_main_success(mocker, mock_triage_report, mock_raw_findings):
    """Test end-to-end execution of the main script."""
    mocker.patch("sys.argv", ["scanner.py", "example.com"])
    
    mock_recon = mocker.patch("bounty_scanner.scanner.run_recon_pipeline", return_value=mock_raw_findings)
    mock_triage = mocker.patch("bounty_scanner.scanner.triage_findings", return_value=mock_triage_report)
    mock_upload = mocker.patch("bounty_scanner.scanner.upload_to_s3")

    main()

    mock_recon.assert_called_once_with("example.com")
    mock_triage.assert_called_once_with(mock_raw_findings)
    mock_upload.assert_called_once_with("example.com", mock_triage_report, mock_raw_findings)

def test_main_missing_args(mocker):
    """Test script exits properly if no domain is provided."""
    mocker.patch("sys.argv", ["scanner.py"])
    
    # Catch the native SystemExit exception instead of mocking it
    with pytest.raises(SystemExit) as excinfo:
        main()
        
    # Verify the exit code was exactly 1
    assert excinfo.value.code == 1