terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.20"
    }
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.35"
    }
  }

  backend "s3" {
    bucket         = "nikkei-financial-rag-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "nikkei-financial-rag-tflocks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "financial-rag-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = "nikkei-b2b-digital-info-unit"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "datadog" {
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
  api_url = var.datadog_api_url
}
