"""Offline evaluation harness: for each user in the held-out test set, rank all
candidate articles with a given model and compute per-user ranking metrics.

Returns per-user metric arrays (not just the mean) because the A/B testing module
needs the raw per-user distribution to run significance tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from newsreco.evaluation.metrics import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k
from newsreco.ingestion.schema import Interaction
from newsreco.models.base import BaseRecommender


@dataclass
class EvalResult:
    model_name: str
    k: int
    per_user: dict[int, dict[str, float]] = field(default_factory=dict)

    def mean(self, metric: str) -> float:
        values = [m[metric] for m in self.per_user.values()]
        return sum(values) / len(values) if values else 0.0

    def summary(self) -> dict[str, float]:
        if not self.per_user:
            return {}
        metrics = next(iter(self.per_user.values())).keys()
        return {m: self.mean(m) for m in metrics}

    def values(self, metric: str) -> list[float]:
        return [m[metric] for m in self.per_user.values()]


def evaluate_model(
    model: BaseRecommender,
    test_interactions: list[Interaction],
    all_article_ids: list[str],
    k: int = 10,
) -> EvalResult:
    relevant_by_user: dict[int, set[str]] = {}
    for it in test_interactions:
        relevant_by_user.setdefault(it.user_id, set()).add(it.article_id)

    result = EvalResult(model_name=model.name, k=k)
    for user_id, relevant in relevant_by_user.items():
        ranked = [aid for aid, _ in model.recommend(user_id, all_article_ids, k=k)]
        result.per_user[user_id] = {
            f"precision@{k}": precision_at_k(ranked, relevant, k),
            f"recall@{k}": recall_at_k(ranked, relevant, k),
            f"ndcg@{k}": ndcg_at_k(ranked, relevant, k),
            f"hit_rate@{k}": hit_rate_at_k(ranked, relevant, k),
            "mrr": mrr(ranked, relevant),
        }
    return result
