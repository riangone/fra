"""FastAPI serving layer for the recommendation model.

Loads whatever version the registry currently marks as `production` at startup
(the pipeline's promotion gate is the only thing that changes what this serves —
the API never trains or auto-promotes anything itself, keeping serving and
training cleanly separated).
"""

from __future__ import annotations

import csv
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from newsreco.ingestion.loader import load_articles
from newsreco.ingestion.schema import EVENT_WEIGHTS
from newsreco.mlops.config import PipelineConfig
from newsreco.mlops.registry import ModelRegistry

logger = logging.getLogger(__name__)

config = PipelineConfig()
_state: dict = {"model": None, "articles": [], "article_by_id": {}, "registry": None}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _load_state()
    yield


app = FastAPI(title="news-recommender-mlops", version="0.1.0", lifespan=_lifespan)


class RecommendationItem(BaseModel):
    article_id: str
    title: str
    category: str
    score: float


class RecommendationResponse(BaseModel):
    user_id: int
    model_version: str
    is_cold_start: bool
    items: list[RecommendationItem]


class EventRequest(BaseModel):
    user_id: int
    article_id: str
    event_type: str = Field(pattern="^(view|click|read_long|like)$")


def _load_state() -> None:
    registry = ModelRegistry(config.artifacts_dir)
    _state["registry"] = registry
    try:
        _state["model"] = registry.load_model("hybrid")
        _state["model_version"] = registry.get_production_version("hybrid")
    except LookupError:
        logger.warning("no production model registered yet; run scripts/run_pipeline.py first")
        _state["model"] = None
        _state["model_version"] = None

    try:
        articles = load_articles(config.data_dir / "articles.json")
    except FileNotFoundError:
        articles = []
    _state["articles"] = articles
    _state["article_by_id"] = {a.id: a for a in articles}


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": _state["model"] is not None,
        "n_articles": len(_state["articles"]),
    }


@app.get("/model/info")
def model_info() -> dict:
    registry: ModelRegistry = _state["registry"]
    info = registry.get_production_info("hybrid")
    if info is None:
        raise HTTPException(status_code=503, detail="no production model registered yet")
    return info


@app.get("/recommend/{user_id}", response_model=RecommendationResponse)
def recommend(user_id: int, k: int = 10) -> RecommendationResponse:
    model = _state["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="no production model registered yet")

    all_ids = list(_state["article_by_id"].keys())
    if not all_ids:
        raise HTTPException(status_code=503, detail="no article catalog loaded")

    is_cold_start = user_id not in getattr(model, "known_users", set())
    ranked = model.recommend(user_id, all_ids, k=k)

    items = [
        RecommendationItem(
            article_id=aid,
            title=_state["article_by_id"][aid].title,
            category=_state["article_by_id"][aid].category,
            score=score,
        )
        for aid, score in ranked
    ]
    return RecommendationResponse(
        user_id=user_id,
        model_version=_state.get("model_version") or "unknown",
        is_cold_start=is_cold_start,
        items=items,
    )


@app.post("/events")
def log_event(event: EventRequest) -> dict:
    """Append a feedback event to the raw interaction log. In a real deployment this
    would publish to a stream (Kafka/PubSub) that ingestion consumes; here it's
    appended directly to the CSV that `scripts/run_pipeline.py` reads on next run,
    which is enough to demonstrate the online-feedback -> offline-retrain loop."""
    if event.article_id not in _state["article_by_id"]:
        raise HTTPException(status_code=404, detail="unknown article_id")

    path: Path = config.data_dir / "interactions.csv"
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["user_id", "article_id", "event_type", "timestamp", "weight"])
        writer.writerow(
            [event.user_id, event.article_id, event.event_type, time.time(), EVENT_WEIGHTS[event.event_type]]
        )
    return {"status": "logged"}
