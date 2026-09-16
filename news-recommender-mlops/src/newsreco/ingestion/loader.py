"""Ingestion layer: load raw articles / interaction logs from disk into typed records.

This is the "データ収集〜前処理" stage of the MLOps pipeline. It is intentionally
file-based (CSV/JSON) so the whole demo runs with zero external services, but the
function boundaries mirror what a real pipeline would look like (extract -> validate
-> normalize) so swapping the source (a warehouse table, a Kafka topic, an internal
CMS API) only touches this module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from newsreco.ingestion.schema import Interaction, Article

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def load_articles(path: Path | None = None) -> list[Article]:
    path = path or DATA_DIR / "articles.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python scripts/generate_synthetic_data.py` first."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    articles: list[Article] = []
    for row in raw:
        articles.append(
            Article(
                id=row["id"],
                title=row["title"],
                content=row["content"],
                category=row.get("category", "その他"),
                ticker=row.get("ticker", ""),
                company_name=row.get("company_name", ""),
                source=row.get("source", "日本経済新聞"),
                date=row.get("date", ""),
            )
        )
    _validate_articles(articles)
    return articles


def load_interactions(path: Path | None = None) -> list[Interaction]:
    path = path or DATA_DIR / "interactions.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python scripts/generate_synthetic_data.py` first."
        )
    interactions: list[Interaction] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            interactions.append(
                Interaction(
                    user_id=int(row["user_id"]),
                    article_id=row["article_id"],
                    event_type=row["event_type"],
                    timestamp=float(row["timestamp"]),
                    weight=float(row["weight"]),
                )
            )
    _validate_interactions(interactions)
    return interactions


def _validate_articles(articles: list[Article]) -> None:
    ids = [a.id for a in articles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate article ids found in ingestion source")
    if not articles:
        raise ValueError("no articles loaded")


def _validate_interactions(interactions: list[Interaction]) -> None:
    if not interactions:
        raise ValueError("no interactions loaded")
    for it in interactions:
        if it.weight <= 0:
            raise ValueError(f"non-positive interaction weight: {it}")


def time_split(
    interactions: list[Interaction], test_fraction: float = 0.2
) -> tuple[list[Interaction], list[Interaction]]:
    """Chronological train/test split (avoids leaking future clicks into training,
    which is the #1 offline-eval mistake in recommender systems)."""
    ordered = sorted(interactions, key=lambda it: it.timestamp)
    cut = int(len(ordered) * (1 - test_fraction))
    return ordered[:cut], ordered[cut:]
