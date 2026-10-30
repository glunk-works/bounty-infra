terraform {
  # Partial backend configuration. 
  # Bucket, region, and dynamodb_table are injected at init: from the production and scan Environments for apply and scans,
  # and bucket + region only from the infra-plan Environment for the PR-time plan (BI-D23).
  backend "s3" {
    key     = "bounty-infra/tofu.tfstate"
    encrypt = true
  }
}