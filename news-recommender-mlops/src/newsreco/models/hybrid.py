"""Hybrid recommender: weighted blend of content-based, collaborative and
popularity scores, with automatic cold-start handling.

Weights default to values tuned via offline evaluation (see
evaluation/offline_eval.py and README) but are constructor args so the A/B
harness can sweep them.
"""

from __future__ import annotations

from newsreco.models.base import BaseRecommender
from newsreco.models.collaborative import CollaborativeRecommender
from newsreco.models.content_based import ContentBasedRecommender
from newsreco.models.popularity import PopularityRecommender


class HybridRecommender(BaseRecommender):
    name = "hybrid"

    def __init__(
        self,
        content_model: ContentBasedRecommender,
        collaborative_model: CollaborativeRecommender,
        popularity_model: PopularityRecommender,
        weights: dict[str, float] | None = None,
        known_users: set[int] | None = None,
    ) -> None:
        self.content_model = content_model
        self.collaborative_model = collaborative_model
        self.popularity_model = popularity_model
        self.weights = weights or {"content": 0.45, "collaborative": 0.35, "popularity": 0.20}
        # users with enough history for the personalized models to be meaningful
        self.known_users = known_users or set(collaborative_model.user_index.keys())

    def score(self, user_id: int, candidate_ids: list[str]) -> dict[str, float]:
        if user_id not in self.known_users:
            # cold start: no read history yet -> pure popularity fallback
            return self.popularity_model.score(user_id, candidate_ids)

        content = self.content_model.score(user_id, candidate_ids)
        collab = self.collaborative_model.score(user_id, candidate_ids)
        pop = self.popularity_model.score(user_id, candidate_ids)

        w = self.weights
        blended = {}
        for aid in candidate_ids:
            blended[aid] = (
                w["content"] * content.get(aid, 0.0)
                + w["collaborative"] * collab.get(aid, 0.0)
                + w["popularity"] * pop.get(aid, 0.0)
            )
        return blended
