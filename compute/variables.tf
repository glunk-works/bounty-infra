variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "instance_type" {
  type    = string
  default = "t3.medium" # Well suited for light threading/mapping
}

variable "volume_size" {
  type    = number
  default = 40
}

variable "operator_ip" {
  type        = string
  description = "Your personal external IP address (e.g., 198.51.100.50/32) for locked down SSH access"
}

variable "public_key" {
  type        = string
  description = "The public SSH key string utilized for machine authentication"
}

variable "findings_bucket_name" {
  type        = string
  description = "Name of the S3 findings bucket provisioned during bootstrap"
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key provisioned during bootstrap"
}