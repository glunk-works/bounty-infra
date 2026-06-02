output "findings_bucket_arn" {
  value = aws_s3_bucket.findings.arn
}

output "kms_key_arn" {
  value = aws_kms_key.findings_key.arn
}