"""End-to-end MLOps pipeline orchestrator.

    ingest -> featurize -> train (3 models) -> offline evaluate -> A/B significance
    test -> registry promotion gate -> serving-drift check

This is deliberately a single readable function rather than a workflow-engine DAG
(Airflow/Dagster/Kubeflow) — the point of the demo is to show the *stages* and the
*decision logic* (promotion gate, drift threshold) that a real orchestrator would
schedule and retry, not to reimplement a scheduler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from newsreco.evaluation.ab_test import ABTestResult, welch_t_test
from newsreco.evaluation.offline_eval import EvalResult, evaluate_model
from newsreco.features.build_features import build_content_features, build_interaction_matrix, category_distribution
from newsreco.ingestion.loader import load_articles, load_interactions, time_split
from newsreco.mlops.config import PipelineConfig
from newsreco.mlops.monitoring import DriftReport, evaluate_drift, log_drift_report
from newsreco.mlops.registry import ModelRegistry
from newsreco.models.collaborative import CollaborativeRecommender
from newsreco.models.content_based import ContentBasedRecommender
from newsreco.models.hybrid import HybridRecommender
from newsreco.models.popularity import PopularityRecommender

logger = logging.getLogger(__name__)


@dataclass
class PipelineReport:
    eval_results: dict[str, EvalResult] = field(default_factory=dict)
    ab_tests: list[ABTestResult] = field(default_factory=list)
    promoted: bool = False
    promotion_reason: str = ""
    registered_version: str = ""
    drift: DriftReport | None = None

    def print_summary(self) -> None:
        print("\n=== Offline evaluation (mean over held-out users) ===")
        for name, result in self.eval_results.items():
            print(f"  {name:>13}: {result.summary()}")

        print("\n=== A/B significance tests (hybrid vs baselines) ===")
        for ab in self.ab_tests:
            print(f"  {ab.summary()}")

        print("\n=== Registry / promotion ===")
        print(f"  registered hybrid as {self.registered_version}; promoted={self.promoted} ({self.promotion_reason})")

        if self.drift:
            print("\n=== Serving drift check (content-mix PSI) ===")
            print(f"  PSI={self.drift.psi:.4f} -> {self.drift.level}")


def run_pipeline(config: PipelineConfig | None = None) -> PipelineReport:
    config = config or PipelineConfig()
    report = PipelineReport()

    # 1) Ingestion
    articles = load_articles(config.data_dir / "articles.json")
    interactions = load_interactions(config.data_dir / "interactions.csv")
    train_interactions, test_interactions = time_split(interactions, config.test_fraction)
    logger.info("loaded %d articles, %d interactions (%d train / %d test)",
                len(articles), len(interactions), len(train_interactions), len(test_interactions))

    all_article_ids = [a.id for a in articles]
    all_user_ids = sorted({it.user_id for it in interactions})

    # 2) Featurization
    content_features = build_content_features(articles)
    interaction_matrix = build_interaction_matrix(
        train_interactions, user_ids=all_user_ids, article_ids=all_article_ids
    )

    # 3) Training
    popularity = PopularityRecommender().fit(train_interactions)
    content_based = ContentBasedRecommender(content_features).fit(train_interactions)
    collaborative = CollaborativeRecommender(n_factors=config.n_factors).fit(interaction_matrix)
    known_users = {it.user_id for it in train_interactions}
    hybrid = HybridRecommender(
        content_based, collaborative, popularity, weights=config.hybrid_weights, known_users=known_users
    )

    # 4) Offline evaluation
    for model in (popularity, content_based, hybrid):
        report.eval_results[model.name] = evaluate_model(
            model, test_interactions, all_article_ids, k=config.top_k
        )

    # 5) A/B significance tests: does the hybrid model *actually* beat each baseline,
    #    or is the improvement within noise given the test population size?
    metric = f"ndcg@{config.top_k}"
    for baseline_name in ("popularity", "content_based"):
        baseline_values = report.eval_results[baseline_name].values(metric)
        hybrid_values = report.eval_results["hybrid"].values(metric)
        ab_result = welch_t_test(baseline_values, hybrid_values, metric=f"{metric} ({baseline_name} vs hybrid)")
        report.ab_tests.append(ab_result)

    # 6) Registry + promotion gate
    registry = ModelRegistry(config.artifacts_dir)
    version_info = registry.register(
        "hybrid",
        hybrid,
        metrics=report.eval_results["hybrid"].summary(),
        meta={"weights": config.hybrid_weights, "n_train_interactions": len(train_interactions)},
    )
    promoted, reason = registry.promote(
        "hybrid", version_info.version, primary_metric=metric, min_lift=config.promotion_min_lift
    )
    report.registered_version = version_info.version
    report.promoted = promoted
    report.promotion_reason = reason

    # 7) Serving drift check: compare training-time content mix against the mix the
    #    *current production model* would actually serve to the test population.
    prod_version = registry.get_production_version("hybrid")
    prod_model = registry.load_model("hybrid", prod_version)
    baseline_dist = category_distribution(articles, [it.article_id for it in train_interactions])
    served_ids: list[str] = []
    for user_id in list(known_users)[:50] or all_user_ids[:50]:
        served_ids.extend(aid for aid, _ in prod_model.recommend(user_id, all_article_ids, k=config.top_k))
    serving_dist = category_distribution(articles, served_ids)
    drift = evaluate_drift(baseline_dist, serving_dist, config.drift_psi_warn, config.drift_psi_critical)
    log_drift_report(drift, config.artifacts_dir / "monitoring" / "drift_log.jsonl", context={"stage": "post_pipeline"})
    report.drift = drift

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline().print_summary()
