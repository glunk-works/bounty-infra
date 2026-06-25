# **🎯 glunk-works/bounty-infra: Agentic Vulnerability Scanning**

bounty-infra is a modern, serverless DevSecOps pipeline that deploys ephemeral, highly secure bug bounty and vulnerability scanning environments.

This repository has recently been overhauled from a persistent EC2/Bash architecture to a **zero-trust, containerized AWS Fargate model** orchestrated by OpenTofu and GitHub Actions. It leverages an autonomous AI triage loop (via Google Gen AI) to contextualize raw scanner telemetry into actionable executive intelligence.

## **🏗️ Architectural Evolution**

**The Legacy Architecture (Deprecated):**

* Relied on persistent Ubuntu EC2 instances.  
* High latency on boot (5+ minutes) to compile Go binaries via user\_data.sh.  
* Required manual teardown workflows to prevent idle compute costs.  
* State and findings buckets were tightly coupled to the compute lifecycle.

**The New Serverless Architecture:**

* **Ephemeral Compute:** Uses AWS Fargate. Costs scale to absolutely zero when scans are not running.  
* **Immutable Execution:** Tools (subfinder, httpx, nuclei) are pre-compiled into a Docker image alongside Python. Boot time is reduced to seconds.  
* **Agentic Triage:** A Python reasoning loop uses pydantic and Gemini 1.5 Flash to strip out false positives, generating a structured executive summary and top 3 critical threats.  
* **Decoupled State:** Persistent storage (Tofu State, DynamoDB Locks, KMS, and the S3 Findings Bucket) has been abstracted to the global-bootstrap repository. This repository is now entirely stateless.

## **📂 Repository Structure**

The codebase strictly separates infrastructure-as-code from the application logic:

bounty-infra/  
├── .github/workflows/  
│   └── scanner-pipeline.yml   \# The unified CI/CD loop (Provision, Build, Scan)  
├── infra/                     \# OpenTofu Infrastructure (Replaces /compute)  
│   ├── backend.tf             \# Partial backend configuration (injected at runtime)  
│   ├── main.tf                \# VPC, Fargate Cluster, ECR, and IAM Task Roles  
│   ├── variables.tf
│   └── outputs.tf
└── src/                       \# Application Payload  
    ├── Dockerfile             \# Multi-stage Go builder & Python runner  
    └── scanner.py             \# The core Agentic reasoning loop and S3 uploader

## **🔒 Security & Zero-Trust Posture**

1. **Zero-Ingress Networking:** The Fargate task operates in a public subnet to allow outbound scanning and ECR image pulls without the $32/mo overhead of an AWS NAT Gateway. However, the Security Group explicitly denies **all** inbound traffic.  
2. **Secretless Authentication:** No long-lived AWS IAM Access Keys are stored in GitHub. We use **Infisical** via OIDC to inject dynamic credentials at runtime.  
3. **Least Privilege IAM:** The execution environment uses two separate IAM roles:  
   * *Execution Role:* Granted to AWS to pull images and write CloudWatch logs.  
   * *Task Role:* Granted to the Python script inside the container, strictly scoped to write to the FINDINGS\_BUCKET\_NAME mapped from global-bootstrap.  
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

1. Navigate to the **Actions** tab in this GitHub repository.  
2. Select the **Deploy Infrastructure & Execute Scan** workflow.  
3. Click **Run workflow**.  
4. Enter your target\_domain (e.g., example.com) into the input prompt.  
5. Click **Run**.

### **The Pipeline Lifecycle**

When triggered, the pipeline automatically:

1. Authenticates to Infisical and AWS via OIDC.  
2. Runs tofu apply on the /infra directory (creating the VPC and ECS cluster if they don't exist, or cleanly verifying them in seconds).  
3. Builds the Docker container from /src and pushes it to your ECR registry.  
4. Triggers the Fargate task via the AWS CLI, injecting the target domain as a runtime override.  
5. The container runs the reconnaissance pipeline, triages the findings with AI, uploads the results to S3, and terminates itself.
