output "api_gateway_endpoint" {
  description = "HTTP API Gateway URL for Serverless FastAPI deployment"
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "lambda_api_arn" {
  description = "ARN of the real-time streaming Lambda function"
  value       = aws_lambda_function.api_serverless.arn
}

output "nightly_batch_lambda_arn" {
  description = "ARN of the nightly TSE market close batch Lambda function"
  value       = aws_lambda_function.batch_worker.arn
}

output "gcp_cloud_run_url" {
  description = "Google Cloud Run service URL"
  value       = google_cloud_run_v2_service.financial_rag_cloudrun.uri
}

output "discovery_engine_datastore_id" {
  description = "ID of Google Cloud Discovery Engine Datastore"
  value       = google_discovery_engine_data_store.nikkei_articles_datastore.data_store_id
}
