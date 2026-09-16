"""
Google Cloud Discovery Engine (Vertex AI Search) Production Adapter Specification.
(Vertex AI Search — unstructured データストア + セマンティック/キーワードハイブリッド検索)

对应日经 JD:
- 「検索：Elasticsearch（KNN + 全文検索）, Google Cloud Discovery Engine」

与 `src/retrieval/es_adapter.py` 同一层次：定义从当前轻量级 Python 混合检索
到 Google Cloud Discovery Engine（`google-cloud-discoveryengine` / REST v1）
的完整生产映射配置与 Search Request 规范，对应
`infra/terraform/gcp_vertex.tf` 里声明的
`google_discovery_engine_data_store.nikkei_articles_datastore` 资源。

与 es_adapter 一样，这是配置/请求构建的规范模块，不在运行时持有网络连接——
本项目的 HybridRetriever 走本地内存 BM25+Dense 实现（见
`src/retrieval/hybrid_retriever.py`），Discovery Engine 是面向生产迁移路径
的适配层，用同样的接口形状（构建请求 dict）便于日后替换为真实 gRPC/REST 调用。
"""

from typing import Any, Dict, List, Optional


class DiscoveryEngineFinancialAdapter:
    """
    针对日经新闻/财报语料的 Google Cloud Discovery Engine (Vertex AI Search)
    データストア構成とハイブリッド検索 Search Request 规范定义。
    """

    @staticmethod
    def get_data_store_config(
        project_id: str = "nikkei-financial-rag",
        location: str = "global",
        data_store_id: str = "nikkei-articles-datastore",
    ) -> Dict[str, Any]:
        """Mirrors `google_discovery_engine_data_store.nikkei_articles_datastore`
        in infra/terraform/gcp_vertex.tf — the DataStore resource shape a
        `discoveryengine_v1.DataStoreServiceClient.create_data_store` call
        would submit."""
        return {
            "parent": f"projects/{project_id}/locations/{location}/collections/default_collection",
            "data_store_id": data_store_id,
            "data_store": {
                "display_name": "Nikkei Articles & Financial Filings",
                "industry_vertical": "GENERIC",
                "solution_types": ["SOLUTION_TYPE_SEARCH"],
                "content_config": "CONTENT_REQUIRED",
                "document_processing_config": {
                    "default_parsing_config": {"digital_parsing_config": {}},
                },
            },
        }

    @staticmethod
    def build_hybrid_search_request(
        query_text: str,
        serving_config: str,
        ticker: str = "",
        top_k: int = 5,
        embedding_vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        构建符合 Discovery Engine `SearchService.Search` v1 API 规范的
        ハイブリッド検索 (BM25 keyword + semantic embedding) Request Body。

        `serving_config` example:
          projects/{project}/locations/global/collections/default_collection/
          engines/{engine}/servingConfigs/default_search
        """
        request: Dict[str, Any] = {
            "servingConfig": serving_config,
            "query": query_text,
            "pageSize": top_k,
            "queryExpansionSpec": {"condition": "AUTO"},
            "spellCorrectionSpec": {"mode": "AUTO"},
            "contentSearchSpec": {
                "snippetSpec": {"returnSnippet": True},
                "summarySpec": {
                    "summaryResultCount": top_k,
                    "includeCitations": True,
                    "ignoreAdversarialQuery": True,
                },
            },
            # Discovery Engine's "search tier" analogue of RRF: ranking blends
            # BM25-style relevance with the datastore's own semantic
            # embedding index automatically when RELEVANCE-based ranking is
            # requested. An explicit embedding_vector is accepted here for
            # symmetry with es_adapter's KNN query and for future custom
            # embedding ranking expressions.
            "rankingExpression": "relevance_score",
        }
        if ticker:
            request["filter"] = f'ticker: ANY("{ticker}")'
        if embedding_vector:
            request["embeddingSpec"] = {
                "embeddingVectors": [
                    {"fieldPath": "dense_embedding", "vector": embedding_vector}
                ]
            }
        return request

    @staticmethod
    def parse_search_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalizes a Discovery Engine `SearchResponse` into the same
        `{id, title, content, score}` shape `HybridRetriever.search` returns,
        so a future swap-in doesn't require changes downstream of retrieval
        (citation extraction, synthesizer prompt building, etc.)."""
        results: List[Dict[str, Any]] = []
        for item in response.get("results", []):
            doc = item.get("document", {})
            struct_data = doc.get("structData", {}) or {}
            derived = doc.get("derivedStructData", {}) or {}
            results.append(
                {
                    "id": doc.get("id", ""),
                    "title": struct_data.get("title", ""),
                    "ticker": struct_data.get("ticker", ""),
                    "content": derived.get("snippets", [{}])[0].get("snippet", "")
                    if derived.get("snippets")
                    else struct_data.get("content", ""),
                    "score": item.get("relevanceScore", 0.0),
                }
            )
        return results
