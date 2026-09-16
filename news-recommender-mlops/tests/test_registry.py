from newsreco.mlops.registry import ModelRegistry


def test_first_version_is_auto_promoted(tmp_path):
    registry = ModelRegistry(tmp_path)
    v1 = registry.register("hybrid", {"dummy": "model"}, metrics={"ndcg@10": 0.30})
    promoted, reason = registry.promote("hybrid", v1.version, primary_metric="ndcg@10", min_lift=0.02)
    assert promoted is True
    assert registry.get_production_version("hybrid") == "v1"


def test_challenger_below_threshold_is_rejected(tmp_path):
    registry = ModelRegistry(tmp_path)
    v1 = registry.register("hybrid", "model_v1", metrics={"ndcg@10": 0.30})
    registry.promote("hybrid", v1.version, primary_metric="ndcg@10", min_lift=0.02)

    v2 = registry.register("hybrid", "model_v2", metrics={"ndcg@10": 0.305})  # +1.7%, below 2% gate
    promoted, reason = registry.promote("hybrid", v2.version, primary_metric="ndcg@10", min_lift=0.02)

    assert promoted is False
    assert registry.get_production_version("hybrid") == "v1"


def test_challenger_above_threshold_is_promoted(tmp_path):
    registry = ModelRegistry(tmp_path)
    v1 = registry.register("hybrid", "model_v1", metrics={"ndcg@10": 0.30})
    registry.promote("hybrid", v1.version, primary_metric="ndcg@10", min_lift=0.02)

    v2 = registry.register("hybrid", "model_v2", metrics={"ndcg@10": 0.40})  # +33%
    promoted, reason = registry.promote("hybrid", v2.version, primary_metric="ndcg@10", min_lift=0.02)

    assert promoted is True
    assert registry.get_production_version("hybrid") == "v2"
    assert registry.load_model("hybrid") == "model_v2"


def test_versions_are_listed_in_order(tmp_path):
    registry = ModelRegistry(tmp_path)
    registry.register("hybrid", "m1", metrics={"ndcg@10": 0.1})
    registry.register("hybrid", "m2", metrics={"ndcg@10": 0.2})
    assert registry.list_versions("hybrid") == ["v1", "v2"]
