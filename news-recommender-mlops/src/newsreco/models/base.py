"""Common recommender interface. Every model (popularity/content/collaborative/hybrid)
implements `score(user_id, candidate_article_ids) -> {article_id: score}` so the
evaluation harness and the API can treat them interchangeably."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseRecommender(ABC):
    name: str = "base"

    @abstractmethod
    def score(self, user_id: int, candidate_ids: list[str]) -> dict[str, float]:
        """Return a relevance score per candidate article id for this user.
        Higher is better. Implementations must handle unknown users/articles
        gracefully (cold start) rather than raising."""
        raise NotImplementedError

    def recommend(self, user_id: int, candidate_ids: list[str], k: int = 10) -> list[tuple[str, float]]:
        scores = self.score(user_id, candidate_ids)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:k]
