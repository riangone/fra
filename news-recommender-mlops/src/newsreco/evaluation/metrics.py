"""Ranking metrics for offline recommender evaluation.

All functions take `ranked_ids` (model output, best first) and `relevant_ids`
(ground-truth items the user actually engaged with in the held-out test window).
"""

from __future__ import annotations

import math


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for aid in top_k if aid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for aid in top_k if aid in relevant_ids)
    return hits / len(relevant_ids)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = ranked_ids[:k]
    dcg = 0.0
    for i, aid in enumerate(top_k):
        if aid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)  # rank is 0-indexed -> +2
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def mrr(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    for i, aid in enumerate(ranked_ids):
        if aid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def hit_rate_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    return 1.0 if any(aid in relevant_ids for aid in ranked_ids[:k]) else 0.0
