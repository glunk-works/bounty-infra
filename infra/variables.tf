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