# 🎯 bounty-infra: Automated Vulnerability Assessment Architecture

`bounty-infra` is an automated OpenTofu IaC pipeline deploying ephemeral, highly secure AWS bug bounty environments via GitHub Actions. It separates isolated, KMS-encrypted S3 storage for persistent findings from dynamically provisioned Ubuntu compute nodes, which automatically bootstrap with industry-standard tools like Nuclei, Amass, and ffuf.

## 🏗️ Architecture Overview

The infrastructure is strictly divided into two lifecycles:

1. **Persistent Bootstrap Stratum (`/bootstrap`):**
   * **Storage:** KMS-encrypted S3 bucket for findings and DynamoDB for state locking.
   * **Security:** Configures **OpenID Connect (OIDC)** federation, eliminating the need for static AWS Access Keys. GitHub Actions assumes a temporary, strictly scoped IAM role to deploy resources.

2. **Ephemeral Compute Stratum (`/compute`):**
   * **Network & Compute:** Deploys a VPC, strict Security Groups (whitelisted to your IP), and an Ubuntu 24.04 LTS instance.
   * **Automation:** User-data scripts automatically install Go, Subfinder, Nuclei, httpx, ffuf, and Amass upon boot. 
   * **Permissions:** Assigns an isolated IAM Instance Profile allowing the machine to write directly to your encrypted findings bucket.

---

## 🚀 Deployment Playbook

### Prerequisites
* [OpenTofu](https://opentofu.org/docs/intro/install/) installed locally (`winget install OpenTofu.OpenTofu` or `brew install opentofu`).
* [AWS CLI](https://aws.amazon.com/cli/) configured locally with administrative access (`aws configure`).
* A GitHub repository to host this code.

### Stage 1: Persistent Initialization (Bootstrap)
You must execute this phase locally **once** to establish the backend state tracking and the GitHub OIDC trust relationship.

1. Clone your repository and navigate to the bootstrap directory:
   ~~~bash
   cd bootstrap
   ~~~
2. Initialize OpenTofu:
   ~~~bash
   tofu init
   ~~~
3. Apply the bootstrap configuration (Provide a globally unique bucket name):
   ~~~bash
   tofu apply -var="bucket_name=your-unique-bounty-archive-01"
   ~~~
4. **Save the Outputs:** When the apply completes, the terminal will output three critical values. Save these for Stage 2:
   * `findings_bucket_arn`
   * `kms_key_arn`
   * `github_actions_deployer_role_arn`

### Stage 2: Bind the Compute Environment
Now that your storage exists, you must tell your compute environment where to save its state.

1. Open `compute/main.tf`.
2. Locate the `backend "s3"` block at the top of the file.
3. Replace the `bucket` value with the exact name of the bucket you just created (e.g., `your-unique-bounty-archive-01`).

### Stage 3: GitHub Actions Configuration
Navigate to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions**.

Create the following **Repository Secrets**:
* `OPERATOR_IP`: Your public IP address in CIDR format (e.g., `203.0.113.5/32`) for SSH whitelisting.
* `OPERATOR_SSH_KEY`: Your public SSH key (`ssh-rsa ...`) for instance access.
* `FINDINGS_BUCKET_NAME`: The name of the S3 bucket created in Stage 1.
* `KMS_KEY_ARN`: The KMS Key ARN output from Stage 1.

*(Note: Because we use OIDC federation, you **do not** need to store AWS Access Keys in GitHub!)*

### Stage 4: Triggering the Pipeline
To deploy the compute node, ensure your `.github/workflows/deploy.yml` is configured with the `github_actions_deployer_role_arn` (from Stage 1) in the AWS credentials step.

Commit your changes and push to the `main` branch:
~~~bash
git add .
git commit -m "Initialize backend and trigger compute deployment"
git push origin main
~~~
GitHub Actions will now assume the OIDC role, validate the code, and spin up your testing environment.

---

## 💻 Accessing Your Node

Once the GitHub Action completes successfully, expand the **Execute Changes (Apply)** step in the Actions log to find your `instance_public_ip`.

Connect via SSH:
~~~bash
ssh ubuntu@<INSTANCE_PUBLIC_IP>
~~~

*Note: The background installation of security tools via `user_data` takes approximately 3-5 minutes after boot. You can track the progress by running `tail -f /var/log/user-data.log` on the machine.*

## 🧹 Teardown

When you are finished testing, you should destroy the compute node to save costs. You can do this by running a manual workflow dispatch in GitHub Actions (if configured) or locally:

~~~bash
cd compute
tofu init
tofu destroy -var="operator_ip=..." -var="public_key=..." -var="findings_bucket_name=..." -var="kms_key_arn=..."
~~~
