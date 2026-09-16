"""Statistical significance testing for comparing two recommender variants.

This is the "データ分析に基づく推薦ロジックの効果検証" / "統計検定の基礎知識" piece of the
job spec: before promoting a new model we don't just look at "mean NDCG went up",
we check whether the difference is statistically distinguishable from noise given
the per-user sample size.

Two complementary tests are provided:
  - Welch's t-test (parametric, fast, standard for A/B metric comparisons where the
    two groups can have unequal variance)
  - A paired bootstrap confidence interval on the mean difference (distribution-free,
    robust to the skewed/zero-inflated distributions typical of ranking metrics)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class ABTestResult:
    metric: str
    mean_a: float
    mean_b: float
    lift: float  # (mean_b - mean_a) / mean_a
    t_statistic: float
    p_value: float
    ci_low: float
    ci_high: float
    significant: bool
    alpha: float

    def summary(self) -> str:
        direction = "improves over" if self.mean_b > self.mean_a else "underperforms"
        sig = "statistically significant" if self.significant else "not statistically significant"
        return (
            f"[{self.metric}] B ({self.mean_b:.4f}) {direction} A ({self.mean_a:.4f}); "
            f"lift={self.lift:+.1%}, p={self.p_value:.4f} ({sig} at alpha={self.alpha}), "
            f"95% CI of diff=[{self.ci_low:.4f}, {self.ci_high:.4f}]"
        )


def welch_t_test(
    values_a: list[float],
    values_b: list[float],
    metric: str = "metric",
    alpha: float = 0.05,
    n_bootstrap: int = 5000,
    random_state: int = 42,
) -> ABTestResult:
    """Compare two independent samples of a per-user ranking metric.

    `values_a` / `values_b` should be paired-by-user-population samples of the same
    metric (e.g. NDCG@10 per user) collected from variant A and variant B of the
    recommender in an offline replay or a live A/B test.
    """
    a = np.asarray(values_a, dtype=float)
    b = np.asarray(values_b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("need at least 2 observations per group for a t-test")

    t_stat, p_value = stats.ttest_ind(b, a, equal_var=False)

    mean_a = float(a.mean())
    mean_b = float(b.mean())
    lift = (mean_b - mean_a) / mean_a if mean_a != 0 else float("inf")

    ci_low, ci_high = _bootstrap_ci_diff_means(a, b, n_bootstrap, random_state)

    return ABTestResult(
        metric=metric,
        mean_a=mean_a,
        mean_b=mean_b,
        lift=lift,
        t_statistic=float(t_stat),
        p_value=float(p_value),
        ci_low=ci_low,
        ci_high=ci_high,
        significant=bool(p_value < alpha),
        alpha=alpha,
    )


def _bootstrap_ci_diff_means(
    a: np.ndarray, b: np.ndarray, n_bootstrap: int, random_state: int, alpha: float = 0.05
) -> tuple[float, float]:
    rng = np.random.default_rng(random_state)
    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample_a = rng.choice(a, size=len(a), replace=True)
        sample_b = rng.choice(b, size=len(b), replace=True)
        diffs[i] = sample_b.mean() - sample_a.mean()
    lo = float(np.percentile(diffs, 100 * (alpha / 2)))
    hi = float(np.percentile(diffs, 100 * (1 - alpha / 2)))
    return lo, hi
