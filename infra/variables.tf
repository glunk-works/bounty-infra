variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "findings_bucket_name" {
  type        = string
  description = "Name of the S3 findings bucket provisioned during bootstrap"
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key provisioned during bootstrap"
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = <<-EOT
    Bootstrap-only. Sets the container image tag on the FIRST apply that
    creates the task definition. After that, `build-image.yml` owns image
    deploys directly against ECS (sha-pinned, immutable tags) and the task
    definition's `lifecycle.ignore_changes` means Tofu never reverts them —
    see the comment on aws_ecs_task_definition.scanner_task in main.tf.
  EOT
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