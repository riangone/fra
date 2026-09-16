"""Feature engineering: content vectors + user-item interaction matrix.

Kept as a standalone, dependency-injectable module so the "featurization" stage of
the MLOps pipeline can be tested in isolation from model training, and so the
vectorizer can be swapped (e.g. for the parent repo's embedding provider in
src/retrieval/embeddings.py) without touching the models.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from newsreco.ingestion.schema import Article, Interaction


@dataclass
class ContentFeatures:
    article_ids: list[str]
    matrix: sparse.csr_matrix  # (n_articles, n_terms), L2-normalized rows
    vectorizer: TfidfVectorizer


@dataclass
class InteractionMatrix:
    user_ids: list[int]
    article_ids: list[str]
    matrix: sparse.csr_matrix  # (n_users, n_articles), implicit-feedback weights
    user_index: dict[int, int]
    article_index: dict[str, int]


def build_content_features(articles: list[Article]) -> ContentFeatures:
    vectorizer = TfidfVectorizer(
        max_features=20_000,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b\w+\b",  # permissive: also matches CJK runs as tokens
        sublinear_tf=True,
    )
    texts = [a.text() for a in articles]
    matrix = vectorizer.fit_transform(texts)
    return ContentFeatures(
        article_ids=[a.id for a in articles], matrix=matrix, vectorizer=vectorizer
    )


def build_interaction_matrix(
    interactions: list[Interaction],
    user_ids: list[int] | None = None,
    article_ids: list[str] | None = None,
) -> InteractionMatrix:
    """Aggregate raw events into a (user x article) implicit-feedback weight matrix.

    Multiple events between the same user/article pair sum their weights (a click
    plus a long read is a stronger signal than either alone).
    """
    if user_ids is None:
        user_ids = sorted({it.user_id for it in interactions})
    if article_ids is None:
        article_ids = sorted({it.article_id for it in interactions})

    user_index = {u: i for i, u in enumerate(user_ids)}
    article_index = {a: i for i, a in enumerate(article_ids)}

    rows, cols, vals = [], [], []
    agg: dict[tuple[int, int], float] = {}
    for it in interactions:
        if it.user_id not in user_index or it.article_id not in article_index:
            continue
        key = (user_index[it.user_id], article_index[it.article_id])
        agg[key] = agg.get(key, 0.0) + it.weight

    for (r, c), v in agg.items():
        rows.append(r)
        cols.append(c)
        vals.append(v)

    matrix = sparse.csr_matrix(
        (vals, (rows, cols)), shape=(len(user_ids), len(article_ids))
    )
    return InteractionMatrix(
        user_ids=user_ids,
        article_ids=article_ids,
        matrix=matrix,
        user_index=user_index,
        article_index=article_index,
    )


def category_distribution(articles: list[Article], article_ids: list[str]) -> dict[str, float]:
    """Category histogram over a set of article ids — used both as a popularity
    prior and as the reference distribution for drift monitoring (PSI)."""
    by_id = {a.id: a for a in articles}
    counts: dict[str, int] = {}
    total = 0
    for aid in article_ids:
        art = by_id.get(aid)
        if art is None:
            continue
        counts[art.category] = counts.get(art.category, 0) + 1
        total += 1
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def normalize_rows(matrix: sparse.csr_matrix) -> sparse.csr_matrix:
    norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A.ravel()
    norms[norms == 0] = 1.0
    inv = sparse.diags(1.0 / norms)
    return inv @ matrix
