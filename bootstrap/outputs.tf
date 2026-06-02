output "findings_bucket_arn" {
  value = aws_s3_bucket.findings.arn
}

output "kms_key_arn" {
  value = aws_kms_key.findings_key.arn
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions_deployer.arn
  description = "The ARN for the GitHub Actions OIDC deployer role"
}