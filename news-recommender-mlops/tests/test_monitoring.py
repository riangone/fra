from newsreco.mlops.monitoring import evaluate_drift, population_stability_index


def test_identical_distributions_have_zero_psi():
    dist = {"a": 0.5, "b": 0.5}
    psi, _ = population_stability_index(dist, dist)
    assert psi == 0.0


def test_shifted_distribution_has_positive_psi():
    baseline = {"a": 0.9, "b": 0.1}
    current = {"a": 0.5, "b": 0.5}
    psi, per_category = population_stability_index(baseline, current)
    assert psi > 0
    assert set(per_category) == {"a", "b"}


def test_evaluate_drift_levels():
    baseline = {"a": 0.9, "b": 0.1}

    ok = evaluate_drift(baseline, {"a": 0.89, "b": 0.11}, warn_threshold=0.1, critical_threshold=0.25)
    assert ok.level == "ok"

    critical = evaluate_drift(baseline, {"a": 0.1, "b": 0.9}, warn_threshold=0.1, critical_threshold=0.25)
    assert critical.level == "critical"
