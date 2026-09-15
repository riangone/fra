"""
Telemetry, APM and Structured Observability Module.
(Datadog APM & OpenSearch / CloudWatch 監視接合レイヤー)

对应日经 JD:
- 「ログ・監視：Datadog（メトリクス・ログ・APM）, OpenSearch（ログ分析）」
- 「サーバーレス／コンテナ等の実行環境がもつ制約を踏まえたパフォーマンス設計」
"""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

logger = logging.getLogger("financial_rag.telemetry")


class APMTracer:
    """
    Datadog APM / OpenTelemetry 兼容追踪器
    注入 trace_id, span_id, service, env, 并输出规范的结构化 JSON 日志
    """

    def __init__(self, service_name: str = "financial-rag-agent", env: str = "production"):
        self.service_name = os.getenv("DD_SERVICE", service_name)
        self.env = os.getenv("DD_ENV", env)
        self.version = os.getenv("DD_VERSION", "1.0.0")

    @asynccontextmanager
    async def trace_span(self, operation_name: str, resource_name: Optional[str] = None, tags: Optional[Dict[str, Any]] = None):
        trace_id = uuid.uuid4().hex[:16]
        span_id = uuid.uuid4().hex[:16]
        start_time = time.perf_counter()

        span_data = {
            "dd.trace_id": trace_id,
            "dd.span_id": span_id,
            "dd.service": self.service_name,
            "dd.env": self.env,
            "dd.version": self.version,
            "operation": operation_name,
            "resource": resource_name or operation_name,
            "status": "IN_PROGRESS",
            "tags": tags or {},
        }

        try:
            yield span_data
            duration_ms = (time.perf_counter() - start_time) * 1000
            span_data["duration_ms"] = round(duration_ms, 2)
            span_data["status"] = "OK"
            self._emit_metric_log(span_data)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            span_data["duration_ms"] = round(duration_ms, 2)
            span_data["status"] = "ERROR"
            span_data["error.type"] = type(exc).__name__
            span_data["error.message"] = str(exc)
            self._emit_metric_log(span_data, level=logging.ERROR)
            raise

    def _emit_metric_log(self, record: Dict[str, Any], level: int = logging.INFO):
        """输出 Datadog Agent 和 OpenSearch 可直接摄取的结构化 JSON 行"""
        record["timestamp"] = time.time()
        log_line = json.dumps(record, ensure_ascii=False)
        if level >= logging.ERROR:
            logger.error(log_line)
        else:
            logger.info(log_line)


# 全局单例
tracer = APMTracer()
