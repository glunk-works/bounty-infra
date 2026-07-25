variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# No resource in this config consumes these two anymore (SE Phase 2 deleted
# the last consumer, aws_iam_policy.s3_write_policy), but
# plan-infra.yml/deploy-infra.yml still pass them via -var=, and OpenTofu
# hard-errors ("Value for undeclared variable") on a -var for a variable the
# root module doesn't declare -- so removing the declaration would break both
# workflows, not just go unused. Drop these (and the matching -var= flags)
# once nothing needs the pass-through.
# tflint-ignore: terraform_unused_declarations
variable "findings_bucket_name" {
  type        = string
  description = "Name of the S3 findings bucket provisioned during bootstrap"
}

# tflint-ignore: terraform_unused_declarations
variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key provisioned during bootstrap"
}

variable "vultr_api_key" {
  type        = string
  sensitive   = true
  description = "Vultr API key (Infisical-sourced) — the vultr provider needs it to plan/apply."
}

variable "vultr_region" {
  type        = string
  default     = "ewr"
  description = "Vultr region for the reserved IP and per-scan VMs. Default ewr (New Jersey), near us-east-1."
}

variable "vultr_plan" {
  type        = string
  default     = "vc2-1c-2gb"
  description = "Vultr instance plan for per-scan VMs — 1 vCPU / 2 GB, matching the retired Fargate task sizing."
}

variable "reserved_ip_enabled" {
  type        = bool
  default     = false
  description = <<-EOT
    SE-MG5: provision the persistent reserved IP only when onboarding a
    program that mandates source-IP registration/deconfliction. Default
    false — zero standing cost until an operator deliberately flips this.
  EOT
}