"""Reranking algorithms and Reciprocal Rank Fusion (RRF)."""

from typing import List, Dict, Any


def compute_rrf_fusion(
    bm25_ranked_ids: List[str],
    dense_ranked_ids: List[str],
    k: int = 60,
    bm25_weight: float = 0.5,
    dense_weight: float = 0.5,
) -> Dict[str, float]:
    """
    Computes Reciprocal Rank Fusion (RRF) scores across BM25 and Dense retrieval lists.
    RRF(d) = w_bm25 / (k + rank_bm25(d)) + w_dense / (k + rank_dense(d))
    """
    scores: Dict[str, float] = {}

    for rank, doc_id in enumerate(bm25_ranked_ids, start=1):
        score = bm25_weight / (k + rank)
        scores[doc_id] = scores.get(doc_id, 0.0) + score

    for rank, doc_id in enumerate(dense_ranked_ids, start=1):
        score = dense_weight / (k + rank)
        scores[doc_id] = scores.get(doc_id, 0.0) + score

    return scores
