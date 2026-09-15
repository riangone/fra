"""
Tests for Nightly Disclosure Batch Pipeline and Observability.
"""

import pytest
from src.batch.nightly_disclosure_batch import NightlyDisclosureBatchProcessor
from src.retrieval.es_adapter import ElasticsearchFinancialMapping
from src.monitoring.telemetry import tracer


@pytest.mark.asyncio
async def test_batch_processor_execution():
    processor = NightlyDisclosureBatchProcessor(concurrency_limit=2)
    tasks = [
        {
            "id": "test_7203",
            "ticker": "7203",
            "query": "トヨタ自動車の通期営業利益について教えてください",
        },
        {
            "id": "test_6758",
            "ticker": "6758",
            "query": "ソニーグループの金融スピンオフ計画",
        },
    ]
    summary = await processor.run_batch(tasks)
    assert summary["total_items"] == 2
    assert summary["success_items"] >= 1
    assert "average_consistency_rate" in summary
    assert len(summary["details"]) == 2


def test_elasticsearch_mapping_and_dsl():
    mapping = ElasticsearchFinancialMapping.get_index_settings_and_mapping()
    assert "mappings" in mapping
    assert "dense_embedding" in mapping["mappings"]["properties"]
    assert mapping["mappings"]["properties"]["dense_embedding"]["similarity"] == "cosine"

    dsl = ElasticsearchFinancialMapping.build_hybrid_rrf_query(
        query_text="トヨタ 営業利益",
        query_vector=[0.1] * 64,
        ticker="7203",
        top_k=5,
    )
    assert "retriever" in dsl
    assert "rrf" in dsl["retriever"]
    assert dsl["retriever"]["rrf"]["rank_constant"] == 60


@pytest.mark.asyncio
async def test_telemetry_span():
    async with tracer.trace_span("unit_test_span", resource_name="pytest") as span:
        assert span["status"] is None or span["status"] == "" or "dd.trace_id" in span
        span["custom_val"] = 123
    assert span["status"] == "OK"
    assert "duration_ms" in span
