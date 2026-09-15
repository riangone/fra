variable "environment" {
  type        = string
  description = "Deployment environment (e.g. prod, staging, dev)"
  default     = "prod"
}

variable "aws_region" {
  type        = string
  description = "AWS Tokyo region for low latency to TSE / JPX servers"
  default     = "ap-northeast-1"
}

variable "gcp_project_id" {
  type        = string
  description = "GCP Project ID for Vertex AI and Discovery Engine"
  default     = "nikkei-generative-ai-prod"
}

variable "gcp_region" {
  type        = string
  description = "GCP Tokyo region for Vertex AI endpoints"
  default     = "asia-northeast1"
}

# AWS Lambda Performance & SLO Constraints
variable "lambda_memory_size" {
  type        = number
  description = "Memory allocated to FastAPI/LangGraph Lambda in MB"
  default     = 2048
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Execution timeout for streaming SSE requests in seconds"
  default     = 60
}

variable "lambda_concurrency_limit" {
  type        = number
  description = "Reserved concurrency to prevent LLM backend rate limiting / quota exhaustion"
  default     = 50
}

variable "provisioned_concurrency" {
  type        = number
  description = "Pre-warmed Lambda instances to eliminate cold start latency (< 500ms SLO)"
  default     = 5
}

# Datadog APM & Monitoring
variable "datadog_api_key" {
  type        = string
  description = "Datadog API Key for metrics and APM traces"
  sensitive   = true
  default     = "mock-datadog-api-key"
}

variable "datadog_app_key" {
  type        = string
  description = "Datadog APP Key"
  sensitive   = true
  default     = "mock-datadog-app-key"
}

variable "datadog_api_url" {
  type        = string
  description = "Datadog API endpoint URL (e.g. https://api.datadoghq.com)"
  default     = "https://api.datadoghq.com"
}
