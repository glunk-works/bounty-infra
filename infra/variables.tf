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