# **🎯 glunk-works/bounty-infra: Agentic Vulnerability Scanning**

bounty-infra is a modern, serverless DevSecOps pipeline that deploys ephemeral, highly secure bug bounty and vulnerability scanning environments.

This repository operates on a **zero-trust, containerized AWS Fargate model** orchestrated by OpenTofu and GitHub Actions. It leverages an autonomous AI triage loop (via Google Gemini 2.5 Flash) to contextualize raw scanner telemetry into actionable executive intelligence.

## **🏗️ Scanner Architecture & Features**

The core vulnerability scanner (src/bounty\_scanner/scanner.py) is designed for high performance, reliability, and cost-efficiency:

* **Memory-Efficient Processing:** To prevent container OOM (Out-of-Memory) crashes during massive scans, the pipeline utilizes disk-backed I/O. Standard outputs from subfinder, httpx, and nuclei are routed directly to temporary files on the container's ephemeral disk and processed line-by-line.  
* **LLM Token Management (AI Triage):** The AI agent automatically filters out "Info" and "Low" severity noise to preserve context window limits. It enforces a hard cap of the top 50 highest-priority findings, explicitly flagging any truncations in the executive summary so the security team is aware of any backlog.  
* **Comprehensive S3 Storage:** Upon completion, the scanner uploads the AI-generated triage report and raw JSON findings to your AWS S3 bucket. It also preserves the raw reconnaissance artifacts (subdomains.txt, live\_hosts.txt, nuclei\_output.jsonl) in an organized /artifacts subfolder for manual review.  
* **Ephemeral Compute:** Powered by AWS Fargate, compute costs scale to absolutely zero when scans are not running.

## **📂 Repository Structure**

The codebase strictly separates infrastructure-as-code from the application logic:

bounty-infra/    
├── .github/workflows/    
│   ├── ci.yml                 \# PR Quality Gates (Lint & Test)  
│   ├── build-and-push.yml     \# 1\. Provision Infra & Build/Push Docker image  
│   └── run-scan.yml           \# 2\. Trigger Fargate Scan & AI Triage  
├── infra/                     \# OpenTofu Infrastructure  
│   ├── backend.tf             \# Partial backend configuration  
│   ├── main.tf                \# VPC, Fargate Cluster, ECR, and IAM Task Roles    
│   ├── variables.tf  
│   └── outputs.tf  
└── src/                       \# Application Payload    
    ├── Dockerfile             \# Multi-stage Go builder & Python runner   
    ├── pyproject.toml         \# Hatch project configuration  
    ├── tests/                 \# Pytest unit tests   
    └── bounty\_scanner/        \# Python module  
        └── scanner.py         \# The core Agentic reasoning loop and S3 uploader

## **🔒 Security & Zero-Trust Posture**

1. **Zero-Ingress Networking:** The Fargate task operates in a public subnet to allow outbound scanning and ECR image pulls without the $32/mo overhead of an AWS NAT Gateway. However, the Security Group explicitly denies **all** inbound traffic.  
2. **Secretless Authentication:** No long-lived AWS IAM Access Keys are stored in GitHub. We use **Infisical** via OIDC to inject dynamic credentials at runtime.  
3. **Least Privilege IAM:** The execution environment uses two separate IAM roles:  
   * *Execution Role:* Granted to AWS to pull images and write CloudWatch logs.  
   * *Task Role:* Granted to the Python script inside the container, strictly scoped to write to the FINDINGS\_BUCKET\_NAME mapped from the bootstrap repository.  
4. **Non-Root Containers:** The Docker container executes all security tools under a restricted sec-ops user group.

## **🚀 Usage & Deployment**

Because this infrastructure is stateless, you do not need to run local initializations. Everything is handled via the GitHub Actions UI.

### **Prerequisites (Infisical)**

Ensure the following variables are populated in your Infisical bounty-infra path:

* AWS\_OIDC\_ROLE\_ARN: The OIDC deployment role from global-bootstrap.  
* AWS\_REGION: e.g., us-east-1  
* TF\_STATE\_BUCKET: The central Terraform state bucket from global-bootstrap.  
* TF\_STATE\_LOCK\_TABLE: The central DynamoDB lock table.  
* FINDINGS\_BUCKET\_NAME: The S3 bucket where JSON reports will be saved.  
* GEMINI\_API\_KEY: Required for the scanner.py LLM triage loop.

### **Running a Scan**

Our pipeline is decoupled to ensure infrastructure health is separated from security state.

**Step 1: Deploy Infrastructure & Image**

*(You only need to run this when code or infrastructure changes.)*

1. Navigate to the **Actions** tab in GitHub.  
2. Select the **1\. Build Infra & Container Image** workflow.  
3. Click **Run workflow**. This provisions the OpenTofu infrastructure, packages the Python module, builds the Docker image, and pushes it to ECR securely.

**Step 2: Execute Vulnerability Scan**

*(Run this as often as you like.)*

1. Select the **2\. Execute Vulnerability Scan** workflow.  
2. Click **Run workflow**.  
3. Enter your target\_domain (e.g., example.com) into the input prompt and run.  
4. The container runs the reconnaissance pipeline, triages the findings with AI, uploads the results to S3, and terminates cleanly.

## **💻 Development Workflow**

This project uses [Hatch](https://hatch.pypa.io/) for dependency management, linting, testing, and packaging. This ensures absolute consistency between local development and our CI/CD pipeline.

### **Prerequisites**

* Python 3.11+  
* [Hatch](https://hatch.pypa.io/latest/install/)

### **Local Development Commands**

Navigate to the src/ directory to run these commands locally:

#### **1\. Quality Gates (Linting & Formatting)**

We use ruff for linting/formatting and bandit for security analysis (configured to alert on Medium/High severities only).

cd src    
hatch run lint:check  \# Check linting, formatting, and security    
hatch run lint:fmt    \# Automatically fix formatting and linting issues

#### **2\. Running Tests**

We use pytest with pytest-mock for comprehensive, isolated unit testing.

cd src    
hatch run test:run    \# Run the full test suite

#### **3\. Packaging**

To build a distribution wheel for the application:

cd src    
hatch build           \# Generates a .whl file in the dist/ directory

## **🔄 CI/CD Pipeline**

Our continuous integration pipeline automates all quality checks:

* **Lint & Test:** Validated on every Pull Request using hatch in the ci.yml workflow.  
* **Packaging:** Built as a deterministic artifact using hatch build during deployment.  
* **Deployment:** Containerized via Docker using the packaged code and pushed seamlessly to AWS ECR.