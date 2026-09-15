# ==============================================================================
# Datadog APM, SLO Tracking & Citation Consistency Alerts
# ==============================================================================

# 1. Synthetic Health Check Monitor (Every 1 minute)
resource "datadog_synthetics_test" "api_health_check" {
  type    = "api"
  subtype = "http"
  name    = "[SLO] Nikkei Financial RAG - /api/v1/health Availability"
  status  = "live"
  message = "Notification: Financial RAG API health check failed! @slack-nikkei-rag-ops"

  locations = ["aws:ap-northeast-1"]

  request_definition {
    method = "GET"
    url    = "https://${aws_apigatewayv2_api.http_api.id}.execute-api.${var.aws_region}.amazonaws.com/api/v1/health"
    timeout = 5
  }

  assertion {
    type     = "statusCode"
    operator = "is"
    target   = "200"
  }

  assertion {
    type     = "responseTime"
    operator = "lessThan"
    target   = "1000"
  }

  options_list {
    tick_every           = 60
    min_failure_duration = 120
    min_location_failed  = 1
  }

  tags = ["env:${var.environment}", "service:financial-rag-agent", "team:nikkei-b2b"]
}

# 2. Citation Consistency Rate SLO Monitor (Quality Assurance for Production RAG)
resource "datadog_monitor" "citation_consistency_slo" {
  name    = "[AI Quality] Citation Attribution Consistency Dropped Below 85%"
  type    = "metric alert"
  message = <<-EOT
    Warning: The sentence-level citation verification engine detected attribution consistency rate dropped below 85%.
    Check recent prompt mutations or retriever drift.
    @slack-nikkei-rag-alerts
  EOT

  query = "avg(last_15m):avg:financial_rag.citation.consistency_rate{env:${var.environment}} < 0.85"

  monitor_thresholds {
    critical = 0.85
    warning  = 0.90
  }

  notify_no_data    = false
  renotify_interval = 60

  tags = ["env:${var.environment}", "service:financial-rag-agent", "type:llm-eval"]
}

# 3. Stream Latency Monitor (SLO: 95% requests finish token generation under 15s)
resource "datadog_monitor" "latency_slo" {
  name    = "[Latency SLO] LangGraph E2E Pipeline Latency Exceeds 15s"
  type    = "metric alert"
  message = <<-EOT
    Alert: E2E multi-step agent latency exceeds 15,000ms.
    Investigate MCP server response times or LLM backend queuing.
    @slack-nikkei-rag-ops
  EOT

  query = "p95(last_10m):avg:financial_rag.latency.e2e_ms{env:${var.environment}} > 15000"

  monitor_thresholds {
    critical = 15000
    warning  = 10000
  }

  tags = ["env:${var.environment}", "service:financial-rag-agent", "slo:latency"]
}
