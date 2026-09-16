"""Popularity baseline: interaction-count weighted by recency decay.

This is both (a) a baseline to beat in offline evaluation and (b) the cold-start
fallback the API falls back to for users with no interaction history.
"""

from __future__ import annotations

import math

from newsreco.ingestion.schema import Interaction
from newsreco.models.base import BaseRecommender


class PopularityRecommender(BaseRecommender):
    name = "popularity"

    def __init__(self, half_life_days: float = 7.0) -> None:
        self.half_life_days = half_life_days
        self._scores: dict[str, float] = {}

    def fit(self, interactions: list[Interaction]) -> "PopularityRecommender":
        if not interactions:
            self._scores = {}
            return self
        now = max(it.timestamp for it in interactions)
        decay = math.log(2) / (self.half_life_days * 86400)
        scores: dict[str, float] = {}
        for it in interactions:
            age = now - it.timestamp
            scores[it.article_id] = scores.get(it.article_id, 0.0) + it.weight * math.exp(-decay * age)
        # normalize to [0, 1] for easy blending with other models
        max_score = max(scores.values()) if scores else 1.0
        self._scores = {aid: s / max_score for aid, s in scores.items()} if max_score > 0 else scores
        return self

    def score(self, user_id: int, candidate_ids: list[str]) -> dict[str, float]:
        return {aid: self._scores.get(aid, 0.0) for aid in candidate_ids}
