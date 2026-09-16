"""Collaborative filtering via matrix factorization (Truncated SVD) over the
implicit-feedback user x article matrix.

`implicit`/Spark-ALS would be the production choice at real scale; TruncatedSVD is
used here to keep the dependency footprint light while preserving the same
interface, so swapping the implementation later is a one-file change.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD

from newsreco.features.build_features import InteractionMatrix
from newsreco.models.base import BaseRecommender


class CollaborativeRecommender(BaseRecommender):
    name = "collaborative"

    def __init__(self, n_factors: int = 32, random_state: int = 42) -> None:
        self.n_factors = n_factors
        self.random_state = random_state
        self.user_factors: np.ndarray | None = None
        self.item_factors: np.ndarray | None = None
        self.user_index: dict[int, int] = {}
        self.article_index: dict[str, int] = {}

    def fit(self, interaction_matrix: InteractionMatrix) -> "CollaborativeRecommender":
        n_factors = min(self.n_factors, min(interaction_matrix.matrix.shape) - 1)
        n_factors = max(n_factors, 1)
        svd = TruncatedSVD(n_components=n_factors, random_state=self.random_state)
        self.user_factors = svd.fit_transform(interaction_matrix.matrix)
        # item_factors: (n_items, n_factors) so that user_factors @ item_factors.T
        # reconstructs the interaction matrix
        self.item_factors = svd.components_.T
        self.user_index = interaction_matrix.user_index
        self.article_index = interaction_matrix.article_index
        return self

    def score(self, user_id: int, candidate_ids: list[str]) -> dict[str, float]:
        u = self.user_index.get(user_id)
        if u is None or self.user_factors is None or self.item_factors is None:
            return {aid: 0.0 for aid in candidate_ids}
        user_vec = self.user_factors[u]
        result: dict[str, float] = {}
        for aid in candidate_ids:
            i = self.article_index.get(aid)
            if i is None:
                result[aid] = 0.0
            else:
                result[aid] = float(np.dot(user_vec, self.item_factors[i]))
        # min-max normalize to [0, 1] within this candidate set for stable blending
        values = np.array(list(result.values()))
        if values.max() > values.min():
            span = values.max() - values.min()
            result = {k: (v - values.min()) / span for k, v in result.items()}
        return result
