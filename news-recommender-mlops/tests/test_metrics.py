from newsreco.evaluation.metrics import hit_rate_at_k, mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_precision_at_k_all_hits():
    assert precision_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_precision_at_k_no_hits():
    assert precision_at_k(["a", "b", "c"], {"x", "y"}, k=3) == 0.0


def test_precision_at_k_partial():
    assert precision_at_k(["a", "b", "c", "d"], {"a", "c"}, k=4) == 0.5


def test_recall_at_k():
    # 1 of 2 relevant items retrieved
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_recall_at_k_empty_relevant():
    assert recall_at_k(["a", "b"], set(), k=2) == 0.0


def test_ndcg_perfect_ranking_is_one():
    ranked = ["a", "b", "c"]
    relevant = {"a", "b"}
    assert ndcg_at_k(ranked, relevant, k=3) == 1.0


def test_ndcg_worse_ranking_scores_lower():
    relevant = {"a", "b"}
    perfect = ndcg_at_k(["a", "b", "c"], relevant, k=3)
    worse = ndcg_at_k(["c", "a", "b"], relevant, k=3)
    assert worse < perfect


def test_ndcg_no_relevant_in_ground_truth_is_zero():
    assert ndcg_at_k(["a", "b"], set(), k=2) == 0.0


def test_mrr_first_position():
    assert mrr(["a", "b", "c"], {"a"}) == 1.0


def test_mrr_third_position():
    assert mrr(["x", "y", "a"], {"a"}) == 1 / 3


def test_mrr_no_hit():
    assert mrr(["x", "y"], {"a"}) == 0.0


def test_hit_rate_at_k():
    assert hit_rate_at_k(["a", "b"], {"b"}, k=2) == 1.0
    assert hit_rate_at_k(["a", "b"], {"z"}, k=2) == 0.0
