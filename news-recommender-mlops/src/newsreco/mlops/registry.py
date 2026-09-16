"""Local, file-system-backed model registry.

Mirrors the core ideas of MLflow's Model Registry / SageMaker Model Registry at a
scale appropriate for a demo:
  - every training run is versioned and immutable once written (artifacts/<name>/vN/)
  - metrics + metadata travel with the model artifact, not in a separate system
  - promotion to "production" is gated: a challenger only replaces the incumbent if
    it clears a minimum relative-lift threshold on the primary metric (and,
    optionally, a statistical significance check from evaluation/ab_test.py)

This makes "which model is live" a single source of truth (`production.json`) that
the serving layer reads, instead of the serving layer trusting whatever the last
training job happened to produce.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


@dataclass
class VersionInfo:
    model_name: str
    version: str
    metrics: dict[str, float]
    meta: dict[str, Any]
    path: Path


class ModelRegistry:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _model_dir(self, model_name: str) -> Path:
        d = self.artifacts_dir / model_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _next_version(self, model_name: str) -> str:
        d = self._model_dir(model_name)
        existing = [
            int(p.name[1:]) for p in d.iterdir() if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
        ]
        return f"v{(max(existing) + 1) if existing else 1}"

    def register(
        self,
        model_name: str,
        model_obj: Any,
        metrics: dict[str, float],
        meta: dict[str, Any] | None = None,
    ) -> VersionInfo:
        version = self._next_version(model_name)
        version_dir = self._model_dir(model_name) / version
        version_dir.mkdir(parents=True, exist_ok=True)

        joblib.dump(model_obj, version_dir / "model.joblib")
        (version_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
        full_meta = {"registered_at": time.time(), **(meta or {})}
        (version_dir / "meta.json").write_text(json.dumps(full_meta, indent=2, ensure_ascii=False))

        return VersionInfo(model_name=model_name, version=version, metrics=metrics, meta=full_meta, path=version_dir)

    def get_metrics(self, model_name: str, version: str) -> dict[str, float]:
        path = self._model_dir(model_name) / version / "metrics.json"
        return json.loads(path.read_text())

    def get_production_version(self, model_name: str) -> str | None:
        path = self._model_dir(model_name) / "production.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())["version"]

    def get_production_info(self, model_name: str) -> dict[str, Any] | None:
        path = self._model_dir(model_name) / "production.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def load_model(self, model_name: str, version: str | None = None) -> Any:
        version = version or self.get_production_version(model_name)
        if version is None:
            raise LookupError(f"no production version registered for {model_name!r}")
        return joblib.load(self._model_dir(model_name) / version / "model.joblib")

    def promote(
        self,
        model_name: str,
        version: str,
        primary_metric: str,
        min_lift: float = 0.02,
        force: bool = False,
    ) -> tuple[bool, str]:
        """Promotion gate: only update production.json if the candidate beats the
        current production model's primary metric by at least `min_lift` (relative),
        or if there is no production model yet. Returns (promoted, reason)."""
        candidate_metrics = self.get_metrics(model_name, version)
        if primary_metric not in candidate_metrics:
            return False, f"candidate is missing primary metric {primary_metric!r}"

        current_version = self.get_production_version(model_name)
        if current_version is None:
            self._write_production(model_name, version, candidate_metrics)
            return True, "no existing production model; promoted as first version"

        if force:
            self._write_production(model_name, version, candidate_metrics)
            return True, "forced promotion"

        current_metrics = self.get_metrics(model_name, current_version)
        current_value = current_metrics.get(primary_metric, 0.0)
        candidate_value = candidate_metrics[primary_metric]

        if current_value == 0:
            lift = float("inf") if candidate_value > 0 else 0.0
        else:
            lift = (candidate_value - current_value) / current_value

        if lift >= min_lift:
            self._write_production(model_name, version, candidate_metrics)
            return True, f"lift {lift:+.1%} >= threshold {min_lift:.1%}"
        return False, f"lift {lift:+.1%} below threshold {min_lift:.1%}; keeping {current_version}"

    def _write_production(self, model_name: str, version: str, metrics: dict[str, float]) -> None:
        path = self._model_dir(model_name) / "production.json"
        payload = {"version": version, "promoted_at": time.time(), "metrics": metrics}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    def list_versions(self, model_name: str) -> list[str]:
        d = self._model_dir(model_name)
        versions = [p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("v")]
        return sorted(versions, key=lambda v: int(v[1:]))
