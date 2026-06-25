terraform {
  # Partial backend configuration. 
  # Bucket, region, and dynamodb_table are injected dynamically via GitHub Actions and Infisical.
  backend "s3" {
    key     = "bounty-infra/tofu.tfstate"
    encrypt = true
  }
}