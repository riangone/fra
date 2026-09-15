"""Evaluation metrics for RAG retrieval and citation attribution."""

from typing import List, Dict, Any


def compute_hit_rate_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int) -> float:
    """Calculates whether at least one expected document appears in the top-k retrieved results."""
    top_k = retrieved_ids[:k]
    for eid in expected_ids:
        if eid in top_k:
            return 1.0
    return 0.0


def compute_mrr(retrieved_ids: List[str], expected_ids: List[str], k: int = 5) -> float:
    """Calculates Mean Reciprocal Rank (MRR@K)."""
    top_k = retrieved_ids[:k]
    for rank, doc_id in enumerate(top_k, start=1):
        if doc_id in expected_ids:
            return 1.0 / rank
    return 0.0


def compute_faithfulness_heuristic(answer: str, expected_keywords: List[str]) -> float:
    """Calculates fraction of expected factual keywords present in the generated answer."""
    if not expected_keywords:
        return 1.0
    matches = sum(1 for kw in expected_keywords if kw in answer)
    return round(matches / len(expected_keywords), 3)
