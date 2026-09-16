"""Pipeline configuration. Kept as a plain dataclass (no external config-management
dependency) but every value that a real deployment would tune is surfaced here
rather than hardcoded inside pipeline logic."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _default_data_dir() -> Path:
    # env override lets tests and containerized deployments point at an isolated
    # directory without touching the shared demo dataset.
    return Path(os.environ.get("NEWSRECO_DATA_DIR", ROOT / "data"))


def _default_artifacts_dir() -> Path:
    return Path(os.environ.get("NEWSRECO_ARTIFACTS_DIR", ROOT / "artifacts"))


@dataclass
class PipelineConfig:
    data_dir: Path = field(default_factory=_default_data_dir)
    artifacts_dir: Path = field(default_factory=_default_artifacts_dir)
    top_k: int = 10
    test_fraction: float = 0.2
    n_factors: int = 32
    hybrid_weights: dict[str, float] = field(
        default_factory=lambda: {"content": 0.45, "collaborative": 0.35, "popularity": 0.20}
    )
    primary_metric: str = "ndcg@10"
    promotion_min_lift: float = 0.02  # require >=2% relative lift over current prod
    promotion_alpha: float = 0.05  # significance threshold for the A/B gate
    drift_psi_warn: float = 0.1
    drift_psi_critical: float = 0.25
