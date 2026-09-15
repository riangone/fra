"""
Elasticsearch / OpenSearch Production Adapter Specification & Query Builder.
(Elasticsearch KNN + BM25 + RRF 融合クエリマッピング)

对应日经 JD:
- 「検索：Elasticsearch（KNN + 全文検索）, Google Cloud Discovery Engine」
- 「全文検索／ベクトル検索エンジン（Elasticsearch / OpenSearch 等）を用いた検索の実装」

本模块定义了从当前轻量级 Python 混合检索到企业级 Elasticsearch 8.x 的完整生产映射配置与 Query DSL 规范。
"""

from typing import Dict, Any, List


class ElasticsearchFinancialMapping:
    """
    针对日经新闻/财报语料的 Elasticsearch 8.x Index Mapping 定义
    同时配置 Kuromoji 日文分词器、双字 Bigram 与 dense_vector 余弦空间
    """

    @staticmethod
    def get_index_settings_and_mapping() -> Dict[str, Any]:
        return {
            "settings": {
                "number_of_shards": 2,
                "number_of_replicas": 1,
                "analysis": {
                    "analyzer": {
                        "nikkei_japanese_analyzer": {
                            "type": "custom",
                            "tokenizer": "kuromoji_tokenizer",
                            "filter": [
                                "kuromoji_baseform",
                                "kuromoji_part_of_speech",
                                "cjk_width",
                                "ja_stop",
                                "kuromoji_stemmer",
                                "lowercase",
                            ],
                        }
                    }
                },
            },
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "ticker": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "nikkei_japanese_analyzer",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "nikkei_japanese_analyzer",
                    },
                    "dense_embedding": {
                        "type": "dense_vector",
                        "dims": 64,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "published_at": {"type": "date"},
                    "source": {"type": "keyword"},
                }
            },
        }

    @staticmethod
    def build_hybrid_rrf_query(
        query_text: str,
        query_vector: List[float],
        ticker: str = "",
        top_k: int = 5,
        rrf_rank_constant: int = 60,
    ) -> Dict[str, Any]:
        """
        构建符合 Elasticsearch 8.x 官方标准的 Reciprocal Rank Fusion (RRF) 混合查询 DSL
        """
        query_dsl: Dict[str, Any] = {
            "retriever": {
                "rrf": {
                    "retrievers": [
                        {
                            "standard": {
                                "query": {
                                    "bool": {
                                        "must": [
                                            {
                                                "multi_match": {
                                                    "query": query_text,
                                                    "fields": ["title^2.0", "content"],
                                                    "type": "best_fields",
                                                }
                                            }
                                        ],
                                        "filter": ([{"term": {"ticker": ticker}}] if ticker else []),
                                    }
                                }
                            }
                        },
                        {
                            "knn": {
                                "field": "dense_embedding",
                                "query_vector": query_vector,
                                "k": top_k * 2,
                                "num_candidates": 100,
                                "filter": ([{"term": {"ticker": ticker}}] if ticker else []),
                            }
                        },
                    ],
                    "rank_constant": rrf_rank_constant,
                    "rank_window_size": top_k * 2,
                }
            },
            "size": top_k,
        }
        return query_dsl
