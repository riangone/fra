"""
Tests for Nightly Disclosure Batch Pipeline and Observability.
"""

import pytest
from src.batch.nightly_disclosure_batch import NightlyDisclosureBatchProcessor
from src.retrieval.es_adapter import ElasticsearchFinancialMapping
from src.retrieval.discovery_engine_adapter import DiscoveryEngineFinancialAdapter
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


def test_discovery_engine_data_store_config():
    config = DiscoveryEngineFinancialAdapter.get_data_store_config(
        project_id="nikkei-financial-rag", data_store_id="nikkei-articles-datastore"
    )
    assert config["data_store_id"] == "nikkei-articles-datastore"
    assert config["data_store"]["solution_types"] == ["SOLUTION_TYPE_SEARCH"]
    assert "nikkei-financial-rag" in config["parent"]


def test_discovery_engine_hybrid_search_request():
    request = DiscoveryEngineFinancialAdapter.build_hybrid_search_request(
        query_text="トヨタ 営業利益",
        serving_config="projects/p/locations/global/collections/default_collection/"
        "engines/e/servingConfigs/default_search",
        ticker="7203",
        top_k=5,
        embedding_vector=[0.1] * 64,
    )
    assert request["query"] == "トヨタ 営業利益"
    assert request["pageSize"] == 5
    assert 'ticker: ANY("7203")' == request["filter"]
    assert request["embeddingSpec"]["embeddingVectors"][0]["fieldPath"] == "dense_embedding"


def test_discovery_engine_parse_search_response():
    response = {
        "results": [
            {
                "document": {
                    "id": "doc_1",
                    "structData": {"title": "トヨタ決算速報", "ticker": "7203"},
                    "derivedStructData": {"snippets": [{"snippet": "営業利益が増加"}]},
                },
                "relevanceScore": 0.87,
            }
        ]
    }
    parsed = DiscoveryEngineFinancialAdapter.parse_search_response(response)
    assert len(parsed) == 1
    assert parsed[0]["id"] == "doc_1"
    assert parsed[0]["ticker"] == "7203"
    assert parsed[0]["content"] == "営業利益が増加"
    assert parsed[0]["score"] == 0.87


@pytest.mark.asyncio
async def test_telemetry_span():
    async with tracer.trace_span("unit_test_span", resource_name="pytest") as span:
        assert span["status"] is None or span["status"] == "" or "dd.trace_id" in span
        span["custom_val"] = 123
    assert span["status"] == "OK"
    assert "duration_ms" in span
