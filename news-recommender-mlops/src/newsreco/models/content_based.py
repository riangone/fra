"""Content-based recommender: TF-IDF cosine similarity between a user's read
history and candidate articles.

The vectorizer is injected via `ContentFeatures` so it can later be swapped for a
dense embedding model (e.g. reusing the parent RAG project's embedding provider)
without changing this class's logic.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from newsreco.features.build_features import ContentFeatures
from newsreco.ingestion.schema import Interaction
from newsreco.models.base import BaseRecommender


class ContentBasedRecommender(BaseRecommender):
    name = "content_based"

    def __init__(self, content_features: ContentFeatures) -> None:
        self.cf = content_features
        self._article_row = {aid: i for i, aid in enumerate(content_features.article_ids)}
        self._user_profile: dict[int, np.ndarray] = {}

    def fit(self, interactions: list[Interaction]) -> "ContentBasedRecommender":
        """Build a user profile vector = weighted average of TF-IDF vectors of
        articles the user has previously engaged with."""
        by_user: dict[int, list[tuple[int, float]]] = {}
        for it in interactions:
            row = self._article_row.get(it.article_id)
            if row is None:
                continue
            by_user.setdefault(it.user_id, []).append((row, it.weight))

        profiles: dict[int, np.ndarray] = {}
        for user_id, rows_weights in by_user.items():
            rows = [r for r, _ in rows_weights]
            weights = np.array([w for _, w in rows_weights], dtype=float)
            weights = weights / weights.sum()
            sub = self.cf.matrix[rows].toarray()
            profile = (weights[:, None] * sub).sum(axis=0)
            profiles[user_id] = profile
        self._user_profile = profiles
        return self

    def score(self, user_id: int, candidate_ids: list[str]) -> dict[str, float]:
        profile = self._user_profile.get(user_id)
        rows = [self._article_row[a] for a in candidate_ids if a in self._article_row]
        valid_ids = [a for a in candidate_ids if a in self._article_row]
        if profile is None or not rows:
            return {aid: 0.0 for aid in candidate_ids}
        cand_matrix = self.cf.matrix[rows]
        sims = cosine_similarity(profile.reshape(1, -1), cand_matrix).ravel()
        result = {aid: 0.0 for aid in candidate_ids}
        result.update({aid: float(s) for aid, s in zip(valid_ids, sims)})
        return result

    def similar_articles(self, article_id: str, k: int = 5) -> list[tuple[str, float]]:
        """Item-to-item similarity, useful for "related articles" widgets and for
        unit-testing that the vectorizer captures topical similarity."""
        row = self._article_row.get(article_id)
        if row is None:
            return []
        sims = cosine_similarity(self.cf.matrix[row], self.cf.matrix).ravel()
        order = np.argsort(-sims)
        out = []
        for idx in order:
            aid = self.cf.article_ids[idx]
            if aid == article_id:
                continue
            out.append((aid, float(sims[idx])))
            if len(out) >= k:
                break
        return out
