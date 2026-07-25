terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.52"
    }
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.32"
    }
  }
}

# Kept through this PR even though no aws_* resource remains below: real
# state still holds the Fargate-era resources this PR deletes from config,
# and Tofu needs the provider config present to plan/execute their destroy
# ("Provider configuration not present" otherwise). Remove this block (and
# required_providers.aws, and var.aws_region) in a follow-up PR once an
# applied plan confirms state holds no aws resources.
provider "aws" {
  region = var.aws_region
}

provider "vultr" {
  api_key = var.vultr_api_key
}

# ==========================================
# VULTR EGRESS COMPUTE (BI-D5 / SE)
# ==========================================
# SE-MG1: hybrid management. This section owns only the two Vultr resources
# that are genuinely long-lived; the per-scan VM itself is created and
# destroyed imperatively by run-scan.yml, the direct heir of the retired
# `ecs run-task` -- putting ephemeral cattle through this state file would
# mean state lock contention and churn on every single scan.

# Free, and reproduces the retired Fargate security group's zero-ingress /
# unrestricted-egress shape at no cost: an empty Vultr firewall group
# default-denies all inbound with zero rules attached, and Vultr never
# filters egress at the instance level, so no egress rule is needed either.
resource "vultr_firewall_group" "scan_vm" {
  description = "bounty-scanner egress-only (no ingress rules attached)"
}

# SE-MG5: zero standing cost by default. Vultr bills a reserved IP for as
# long as it exists (detaching doesn't stop the meter, only deleting does),
# so this is provisioned only when the operator onboards a program that
# mandates source-IP registration -- flip reserved_ip_enabled and apply.
# run-scan.yml always detaches (never deletes) on every scan exit path, so
# an enabled reserved IP survives scan-to-scan once provisioned.
resource "vultr_reserved_ip" "scan_vm" {
  count   = var.reserved_ip_enabled ? 1 : 0
  region  = var.vultr_region
  ip_type = "v4"
  label   = "bounty-scanner-reserved-ip"
}
