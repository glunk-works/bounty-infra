# 🎯 glunk-works/bounty-infra: Agentic Vulnerability Scanning

`bounty-infra` is a modern, serverless DevSecOps pipeline that deploys ephemeral, highly secure bug bounty and vulnerability scanning environments.

This repository operates on a **zero-trust, ephemeral-VM model**: each scan boots a per-scan Vultr VM from a public container image, runs, writes to S3, and is destroyed — orchestrated by OpenTofu (for the small set of persistent Vultr resources) and GitHub Actions. It leverages an autonomous AI triage loop (via Google Gemini 2.5 Flash) to contextualize raw scanner telemetry into actionable executive intelligence.

## 🏗️ Scanner Architecture & Features

The core vulnerability scanner (`src/bounty_scanner/scanner.py`) is designed for high performance, reliability, and cost-efficiency:

* **Engine-Level Filtering:** To optimize execution speed and drastically reduce per-scan VM run time, severity filtering happens directly at the tool engine level (`nuclei -s`). This prevents the pipeline from processing unnecessary "Info" or "Low" noise.

* **Dynamic CLI Configuration:** The scanner is built around `argparse`, making it completely modular. Scan parameters such as timeouts, target severities, and AI chunk limits are fed as explicit flags natively from the GitHub Actions UI.

* **Memory-Efficient Processing:** To prevent container OOM (Out-of-Memory) crashes during massive scans, the pipeline utilizes disk-backed I/O. Standard outputs from `subfinder`, `httpx`, and `nuclei` are routed directly to temporary files on the container's ephemeral disk and processed line-by-line.

* **LLM Token Management (AI Triage):** The AI agent strictly manages context window limits. It enforces a hard cap of the top findings (defaulting to 50), explicitly flagging any truncations in the executive summary so the security team is aware of any backlog.

* **Comprehensive S3 Storage:** Upon completion, the scanner uploads the AI-generated triage report and raw JSON findings to your AWS S3 bucket. It also preserves the raw reconnaissance artifacts (`subdomains.txt`, `live_hosts.txt`, `nuclei_output.jsonl`) in an organized `/artifacts` subfolder for manual review.

## 📂 Repository Structure

The codebase strictly separates infrastructure-as-code from the application logic:

```
bounty-infra/  
├── .github/workflows/  
│   ├── ci.yml                 # PR Quality Gates (Lint & Test)
│   ├── build-image.yml        # 1. Build & push the scanner image to GHCR (public, sha-pinned)
│   ├── plan-infra.yml         # tofu plan on PRs touching infra/**
│   ├── deploy-infra.yml       # tofu apply on merge, behind a protected Environment
│   └── run-scan.yml           # 2. Assume a scoped STS session, launch a per-scan Vultr VM, poll for the result
├── infra/                     # OpenTofu Infrastructure (Vultr only — persistent resources)
│   ├── backend.tf             # Partial backend configuration (AWS S3 state, unrelated to scan compute)
│   ├── main.tf                # Vultr firewall group + optional reserved IP (SE-MG5, off by default)
│   ├── scan-vm-userdata.sh.tftpl  # Cloud-init template the launcher renders per scan
│   ├── variables.tf
│   └── outputs.tf
└── src/                       # Application Payload  
    ├── Dockerfile             # Multi-stage Go builder & Python runner 
    ├── pyproject.toml         # Hatch project configuration
    ├── tests/                 # Pytest unit tests 
    └── bounty_scanner/        # Python module
        └── scanner.py         # The core Agentic reasoning loop and S3 uploader
```

## 🔒 Security & Zero-Trust Posture

1. **Zero-Ingress Networking:** The per-scan Vultr VM carries **no inbound firewall rules at all** (an empty Vultr firewall group default-denies all ingress) and pulls a **public** GHCR image, so it needs no inbound port and no pull credential.

2. **Secretless, Short-Lived Authentication:** No long-lived AWS IAM Access Keys are stored in GitHub. `run-scan.yml` authenticates via OIDC, then `sts:AssumeRole`s into a dedicated `bounty-scanner-s3-writer` role (owned by `global-bootstrap`) with an inline **session policy** scoped to just this scan — write access to the target domain's findings prefix, read access to that program's RoE object, and the run's own status-sentinel key — for a duration bounded by the scan timeout. Those short-lived session credentials, never a long-lived key, ride into the VM via cloud-init user-data.

3. **Least-Privilege, Per-Scan IAM:** There is no standing task role to over-provision — the session policy above is generated fresh per invocation and evaporates when the session expires. This replaced the original always-on Fargate task role ([#11](https://github.com/glunk-works/bounty-infra/issues/11)).

4. **Non-Root Containers:** The Docker container executes all security tools under a restricted `sec-ops` user group.

5. **Zero Standing Compute Cost:** Every resource in `infra/` is either free (the firewall group) or provisioned only on deliberate operator action (the reserved IP, off by default) — a scan dispatched without it creates a VM, runs, and destroys it, leaving nothing behind.

## 🚀 Usage & Deployment

Because this infrastructure is stateless, you do not need to run local initializations. Everything is handled via the GitHub Actions UI.

### Prerequisites (Infisical)

Ensure the following variables are populated in your Infisical `bounty-infra` path:

* `AWS_OIDC_ROLE_ARN`: The OIDC deployment role from global-bootstrap.

* `AWS_SCANNER_WRITER_ROLE_ARN`: The `bounty-scanner-s3-writer` role (global-bootstrap) `run-scan.yml` assumes-into for a short-lived, per-scan-scoped S3-write session (SE-MG2).

* `AWS_REGION`: e.g., us-east-1

* `TF_STATE_BUCKET`: The central Terraform state bucket from global-bootstrap.

* `TF_STATE_LOCK_TABLE`: The central DynamoDB lock table.

* `FINDINGS_BUCKET_NAME`: The S3 bucket where JSON reports will be saved.

* `KMS_KEY_ARN`: The KMS key (global-bootstrap) encrypting the findings bucket.

* `VULTR_API_KEY`: Used both by the `vultr` OpenTofu provider and by `run-scan.yml` to create/poll/destroy the per-scan VM directly.

* `GEMINI_API_KEY`: Required for the `scanner.py` LLM triage loop.

### Running a Scan

Our pipeline is decoupled to ensure infrastructure health is separated from security state.

**Step 1: Build & Push the Scanner Image**
*(You only need to run this when `src/` changes — it runs automatically on merge to main, or dispatch it manually.)*

1. Navigate to the **Actions** tab in GitHub.

2. Select the **1b. Build & Push Image** workflow.

3. Click **Run workflow**. This builds the Docker image and pushes it **public, sha-tagged, no `:latest`** to `ghcr.io/glunk-works/bounty-scanner`. It touches no AWS resource.

**Step 2: Execute Vulnerability Scan**
*(Run this as often as you like.)*

1. Select the **2. Execute Vulnerability Scan** workflow.

2. Click **Run workflow**.

3. A customizable form will appear allowing you to inject CLI flags (Target Domain, RoE Program, Image Tag, Target Severities, Timeout, and Max Findings).

4. Enter your parameters and click **Run**.

5. The workflow assumes a scoped STS session, boots a per-scan Vultr VM with that session injected via cloud-init, and polls S3 for a status sentinel the VM writes on exit. The container runs the reconnaissance pipeline, triages the findings with AI, uploads the results to S3, and the workflow always destroys the VM (success, failure, or timeout) before finishing.

## 💻 Development Workflow

This project uses [Hatch](https://hatch.pypa.io/) for dependency management, linting, testing, and packaging. This ensures absolute consistency between local development and our CI/CD pipeline.

### Prerequisites

* Python 3.11+

* [Hatch](https://hatch.pypa.io/latest/install/)

### Local Development Commands

Navigate to the `src/` directory to run these commands locally:

#### 1. Quality Gates (Linting & Formatting)

We use `ruff` for linting/formatting and `bandit` for security analysis (configured to alert on Medium/High severities only).

```
cd src  
hatch run lint:check  # Check linting, formatting, and security  
hatch run lint:fmt    # Automatically fix formatting and linting issues
```

#### 2. Running Tests

We use `pytest` with `pytest-mock` for comprehensive, isolated unit testing.

```
cd src  
hatch run test:run    # Run the full test suite
```

#### 3. Packaging

To build a distribution wheel for the application:

```
cd src  
hatch build           # Generates a .whl file in the dist/ directory
```

## 🔄 CI/CD Pipeline

Our continuous integration pipeline automates all quality checks:

* **Lint & Test:** Validated on every Pull Request using `hatch` in the `ci.yml` workflow.

* **Packaging:** Built as a deterministic artifact using `hatch build` during deployment.

* **Deployment:** Containerized via Docker using the packaged code and pushed publicly to GHCR (sha-tagged, no `:latest`); no AWS credential touches the build path.
