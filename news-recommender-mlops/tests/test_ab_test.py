import random

import pytest

from newsreco.evaluation.ab_test import welch_t_test


def test_identical_distributions_are_not_significant():
    rng = random.Random(0)
    a = [rng.gauss(0.3, 0.05) for _ in range(200)]
    b = [rng.gauss(0.3, 0.05) for _ in range(200)]
    result = welch_t_test(a, b, metric="ndcg@10")
    assert not result.significant
    assert 0.0 <= result.p_value <= 1.0


def test_clearly_separated_distributions_are_significant():
    rng = random.Random(0)
    a = [rng.gauss(0.20, 0.03) for _ in range(200)]
    b = [rng.gauss(0.40, 0.03) for _ in range(200)]
    result = welch_t_test(a, b, metric="ndcg@10")
    assert result.significant
    assert result.mean_b > result.mean_a
    assert result.lift == pytest.approx((result.mean_b - result.mean_a) / result.mean_a)
    # the 95% CI of the mean difference should not straddle zero when the effect is real
    assert result.ci_low > 0


def test_requires_minimum_sample_size():
    with pytest.raises(ValueError):
        welch_t_test([0.1], [0.2])
