"""Lightweight drift monitoring using Population Stability Index (PSI).

In production this would run on a schedule against fresh feature snapshots; here it
compares the category distribution of articles seen at training time against a
"serving-time batch" (e.g. what was actually recommended/clicked today) and logs a
structured alert if the distributions have drifted apart, exactly the signal that
would tell an MLOps engineer "the recommender's assumptions about the content mix
are stale, consider retraining."
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

PSI_EPSILON = 1e-6


@dataclass
class DriftReport:
    psi: float
    level: str  # "ok" | "warn" | "critical"
    per_category: dict[str, float]


def population_stability_index(
    baseline: dict[str, float], current: dict[str, float]
) -> tuple[float, dict[str, float]]:
    """PSI = sum((current% - baseline%) * ln(current% / baseline%)) over categories.

    Rule of thumb: <0.1 no significant shift, 0.1-0.25 moderate shift (investigate),
    >0.25 major shift (retrain / alert).
    """
    categories = set(baseline) | set(current)
    per_category: dict[str, float] = {}
    total = 0.0
    for cat in categories:
        b = baseline.get(cat, 0.0) + PSI_EPSILON
        c = current.get(cat, 0.0) + PSI_EPSILON
        contribution = (c - b) * (_ln(c) - _ln(b))
        per_category[cat] = contribution
        total += contribution
    return total, per_category


def _ln(x: float) -> float:
    import math

    return math.log(x)


def evaluate_drift(
    baseline: dict[str, float],
    current: dict[str, float],
    warn_threshold: float = 0.1,
    critical_threshold: float = 0.25,
) -> DriftReport:
    psi, per_category = population_stability_index(baseline, current)
    if psi >= critical_threshold:
        level = "critical"
    elif psi >= warn_threshold:
        level = "warn"
    else:
        level = "ok"
    return DriftReport(psi=psi, level=level, per_category=per_category)


def log_drift_report(report: DriftReport, log_path: Path, context: dict | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "psi": report.psi,
        "level": report.level,
        "per_category": report.per_category,
        **(context or {}),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
