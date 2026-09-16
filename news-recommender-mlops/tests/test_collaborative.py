from newsreco.features.build_features import build_interaction_matrix
from newsreco.ingestion.schema import Interaction
from newsreco.models.collaborative import CollaborativeRecommender


def _two_cluster_interactions():
    interactions = []
    # cluster A: users 1,2,3 all engage with articles a,b,c
    for user in (1, 2, 3):
        for article in ("a", "b", "c"):
            interactions.append(Interaction(user_id=user, article_id=article, event_type="click", timestamp=1.0, weight=2.0))
    # cluster B: users 4,5,6 all engage with articles x,y,z
    for user in (4, 5, 6):
        for article in ("x", "y", "z"):
            interactions.append(Interaction(user_id=user, article_id=article, event_type="click", timestamp=1.0, weight=2.0))
    return interactions


def test_collaborative_learns_cluster_structure():
    interactions = _two_cluster_interactions()
    matrix = build_interaction_matrix(interactions)
    model = CollaborativeRecommender(n_factors=2).fit(matrix)

    # user 1 (cluster A) should score cluster-A articles higher than cluster-B ones,
    # even though user 1 never directly interacted with article "b" being scored
    # relative to "z" here -- that's the point of collaborative filtering.
    scores = model.score(1, ["b", "c", "x", "y", "z"])
    cluster_a_scores = [scores["b"], scores["c"]]
    cluster_b_scores = [scores["x"], scores["y"], scores["z"]]
    assert min(cluster_a_scores) > max(cluster_b_scores)


def test_collaborative_unknown_user_returns_zeros():
    interactions = _two_cluster_interactions()
    matrix = build_interaction_matrix(interactions)
    model = CollaborativeRecommender(n_factors=2).fit(matrix)
    scores = model.score(999, ["a", "b"])
    assert scores == {"a": 0.0, "b": 0.0}
