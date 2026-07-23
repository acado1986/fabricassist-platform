terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.90"
    }
  }

  # Configure an encrypted, locked remote backend at init time:
  # tofu init -backend-config=../backend-staging.hcl
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "fabricassist"
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}
