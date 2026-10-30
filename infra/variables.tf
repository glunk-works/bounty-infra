variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vultr_api_key" {
  type        = string
  sensitive   = true
  description = "Vultr API key (read from SSM) for apply. The PR-time plan passes a placeholder and runs -refresh=false (BI-D23)."
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