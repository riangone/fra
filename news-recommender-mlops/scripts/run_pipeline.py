"""CLI entrypoint for the MLOps pipeline: train -> evaluate -> A/B test -> promote
-> drift check. Run `python scripts/generate_synthetic_data.py` first if
data/articles.json and data/interactions.csv don't exist yet."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from newsreco.mlops.pipeline import run_pipeline  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    report = run_pipeline()
    report.print_summary()


if __name__ == "__main__":
    main()
