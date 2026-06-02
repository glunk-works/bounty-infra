terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ==========================================
# 1. PERSISTENT STORAGE & SECURITY FOUNDATION
# ==========================================

# KMS Key for Finding Encryption
resource "aws_kms_key" "findings_key" {
  description             = "KMS Key for Bug Bounty Findings S3 Bucket"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name      = "vms-kms-findings"
    ManagedBy = "OpenTofu"
  }
}

# Persistent S3 Bucket for Findings
resource "aws_s3_bucket" "findings" {
  bucket        = var.bucket_name
  force_destroy = false

  tags = {
    Name      = "vms-s3-findings"
    ManagedBy = "OpenTofu"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "findings_encryption" {
  bucket = aws_s3_bucket.findings.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.findings_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "findings_privacy" {
  bucket = aws_s3_bucket.findings.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB Table for OpenTofu State Locking
resource "aws_dynamodb_table" "tofu_locks" {
  name         = "vms-tofu-lock-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name      = "vms-dynamodb-locks"
    ManagedBy = "OpenTofu"
  }
}

# ==========================================
# 2. MODERN OIDC AUTHENTICATION FOR GITHUB
# ==========================================

# Establish the trust relationship with GitHub's OIDC token authority
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8516e8748507a656002f52074eef743c3"]
}

# The IAM Role that GitHub Actions will temporarily assume to run 'tofu apply'
resource "aws_iam_role" "github_actions_deployer" {
  name = "vms-github-actions-deployer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRoleWithWebIdentity"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Strict scoping: Only allows executions coming from your specific repo and main branch
            "token.actions.githubusercontent.com:sub" = "repo:Seuss27/bounty-infra:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}
# Attach administrative or power-user permissions to the deployer role 
# so it can build the compute networks, security groups, and EC2 instances.
resource "aws_iam_role_policy_attachment" "deployer_poweruser" {
  role       = aws_iam_role.github_actions_deployer.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}