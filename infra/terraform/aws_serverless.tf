# ==============================================================================
# AWS Serverless Infrastructure: FastAPI SSE Streaming & Scheduled Batch RAG
# ==============================================================================

# 1. ECR Repository for containerized Lambda packaging
resource "aws_ecr_repository" "agent_repo" {
  name                 = "nikkei/financial-rag-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# 2. IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_exec_role" {
  name = "nikkei-financial-rag-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 3. CloudWatch Log Group with retention policy
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/nikkei-financial-rag-api"
  retention_in_days = 30
}

# 4. Lambda Function for Realtime FastAPI Streaming & LangGraph
resource "aws_lambda_function" "api_serverless" {
  function_name = "nikkei-financial-rag-api"
  role          = aws_iam_role.lambda_exec_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.agent_repo.repository_url}:latest"

  memory_size                    = var.lambda_memory_size
  timeout                        = var.lambda_timeout_seconds
  reserved_concurrent_executions = var.lambda_concurrency_limit

  environment {
    variables = {
      APP_ENV           = var.environment
      DATA_SOURCE_MODE  = "live_api"
      DD_SERVICE        = "financial-rag-agent"
      DD_ENV            = var.environment
      DD_VERSION        = "1.0.0"
      AWS_LWA_INVOKE_MODE = "response_stream" # Lambda Web Adapter SSE streaming mode
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_logs,
    aws_iam_role_policy_attachment.lambda_basic_execution
  ]
}

# 5. Provisioned Concurrency Alias (Eliminates Cold Starts for < 500ms SLO)
resource "aws_lambda_alias" "live_alias" {
  name             = "live"
  description      = "Active production alias with warm concurrency pool"
  function_name    = aws_lambda_function.api_serverless.function_name
  function_version = aws_lambda_function.api_serverless.version
}

resource "aws_lambda_provisioned_concurrency_config" "cold_start_mitigation" {
  function_name                     = aws_lambda_alias.live_alias.function_name
  provisioned_concurrent_executions = var.provisioned_concurrency
  qualifier                         = aws_lambda_alias.live_alias.name
}

# 6. API Gateway v2 (HTTP API with Streaming Support)
resource "aws_apigatewayv2_api" "http_api" {
  name          = "nikkei-financial-rag-gateway"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://f.0101.click", "http://localhost:8000", "http://localhost:8800"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization", "x-trace-id", "traceparent"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.live_alias.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  response_parameters {
    status_code = "200"
    mappings = {
      "append:header.X-Accel-Buffering" = "$context.responseLatency"
    }
  }
}

resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "prod_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_serverless.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
  qualifier     = aws_lambda_alias.live_alias.name
}

# ==============================================================================
# 7. Non-User-Triggered Periodic Scheduled Batch (東証引け後 15:30 JST 自動開示バッチ)
# ==============================================================================

resource "aws_cloudwatch_event_rule" "nightly_tse_disclosure" {
  name                = "tse-market-close-batch-trigger"
  description         = "Triggers nightly batch processing after Tokyo Stock Exchange closing (15:30 JST / 06:30 UTC)"
  schedule_expression = "cron(30 6 ? * MON-FRI *)"
}

resource "aws_lambda_function" "batch_worker" {
  function_name = "nikkei-disclosure-nightly-batch"
  role          = aws_iam_role.lambda_exec_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.agent_repo.repository_url}:latest"
  image_config {
    command = ["python", "-m", "src.batch.nightly_disclosure_batch"]
  }

  memory_size = 3072
  timeout     = 900 # 15 minutes max for full TSE universe batch

  environment {
    variables = {
      APP_ENV          = var.environment
      BATCH_CONCURRENCY = "5"
      DATA_SOURCE_MODE = "live_api"
    }
  }
}

resource "aws_cloudwatch_event_target" "trigger_batch_target" {
  rule      = aws_cloudwatch_event_rule.nightly_tse_disclosure.name
  target_id = "NightlyBatchLambda"
  arn       = aws_lambda_function.batch_worker.arn
}

resource "aws_lambda_permission" "allow_eventbridge_batch" {
  statement_id  = "AllowEventBridgeTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.batch_worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.nightly_tse_disclosure.arn
}
