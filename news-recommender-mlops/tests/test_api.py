"""Integration test for the FastAPI serving layer.

Builds a tiny, hermetic dataset in a tmp dir, points the pipeline at it via the
NEWSRECO_DATA_DIR / NEWSRECO_ARTIFACTS_DIR env overrides (see mlops/config.py),
trains+registers a real model, then re-imports the API module so its module-level
config picks up the isolated paths, and exercises it through FastAPI's TestClient.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

from newsreco.mlops.config import PipelineConfig
from newsreco.mlops.pipeline import run_pipeline

ARTICLES = [
    {"id": "a1", "title": "決算好調", "content": "営業利益が増加した 決算 業績 決算 増益", "category": "決算"},
    {"id": "a2", "title": "決算堅調", "content": "増益となった 決算 業績 決算 好調", "category": "決算"},
    {"id": "a3", "title": "人気記事", "content": "スポーツの試合結果 試合 選手 優勝", "category": "スポーツ"},
]


def _write_dataset(data_dir) -> None:
    (data_dir / "articles.json").write_text(json.dumps(ARTICLES, ensure_ascii=False), encoding="utf-8")
    now = time.time()
    with (data_dir / "interactions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "article_id", "event_type", "timestamp", "weight"])
        for i in range(30):
            ts = now - i * 3600
            writer.writerow([1, "a1", "click", ts, 2.0])
            writer.writerow([1, "a2", "read_long", ts, 3.0])
            writer.writerow([2, "a3", "view", ts, 1.0])


@pytest.fixture(scope="module")
def api_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    artifacts_dir = tmp_path_factory.mktemp("artifacts")
    _write_dataset(data_dir)

    config = PipelineConfig(data_dir=data_dir, artifacts_dir=artifacts_dir, test_fraction=0.2)
    run_pipeline(config)

    os.environ["NEWSRECO_DATA_DIR"] = str(data_dir)
    os.environ["NEWSRECO_ARTIFACTS_DIR"] = str(artifacts_dir)
    sys.modules.pop("newsreco.serving.api", None)
    api_module = importlib.import_module("newsreco.serving.api")

    with TestClient(api_module.app) as client:
        yield client

    os.environ.pop("NEWSRECO_DATA_DIR", None)
    os.environ.pop("NEWSRECO_ARTIFACTS_DIR", None)
    sys.modules.pop("newsreco.serving.api", None)


def test_health_reports_model_loaded(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_loaded"] is True
    assert body["n_articles"] == 3


def test_model_info_returns_production_metadata(api_client):
    resp = api_client.get("/model/info")
    assert resp.status_code == 200
    assert resp.json()["version"] == "v1"


def test_recommend_known_user(api_client):
    resp = api_client.get("/recommend/1?k=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == 1
    assert body["is_cold_start"] is False
    assert len(body["items"]) == 2


def test_recommend_cold_start_user_falls_back(api_client):
    resp = api_client.get("/recommend/9999?k=2")
    assert resp.status_code == 200
    assert resp.json()["is_cold_start"] is True


def test_log_event_appends_and_rejects_unknown_article(api_client):
    ok = api_client.post("/events", json={"user_id": 1, "article_id": "a1", "event_type": "click"})
    assert ok.status_code == 200

    bad = api_client.post("/events", json={"user_id": 1, "article_id": "does-not-exist", "event_type": "click"})
    assert bad.status_code == 404
