from newsreco.features.build_features import build_content_features, build_interaction_matrix
from newsreco.ingestion.schema import Article, Interaction
from newsreco.models.collaborative import CollaborativeRecommender
from newsreco.models.content_based import ContentBasedRecommender
from newsreco.models.hybrid import HybridRecommender
from newsreco.models.popularity import PopularityRecommender

ARTICLES = [
    Article(id="a1", title="決算好調", content="営業利益が増加した 決算 業績", category="決算"),
    Article(id="a2", title="決算堅調", content="増益となった 決算 業績", category="決算"),
    Article(id="a3", title="人気記事", content="スポーツの試合結果", category="スポーツ"),
]

INTERACTIONS = [
    Interaction(user_id=1, article_id="a1", event_type="click", timestamp=1.0, weight=2.0),
    Interaction(user_id=1, article_id="a2", event_type="read_long", timestamp=2.0, weight=3.0),
    Interaction(user_id=2, article_id="a3", event_type="view", timestamp=1.0, weight=1.0),
    Interaction(user_id=2, article_id="a3", event_type="view", timestamp=2.0, weight=1.0),
]


def _build_hybrid():
    cf = build_content_features(ARTICLES)
    content = ContentBasedRecommender(cf).fit(INTERACTIONS)
    matrix = build_interaction_matrix(INTERACTIONS)
    collab = CollaborativeRecommender(n_factors=1).fit(matrix)
    popularity = PopularityRecommender().fit(INTERACTIONS)
    known_users = {it.user_id for it in INTERACTIONS}
    return HybridRecommender(content, collab, popularity, known_users=known_users)


def test_known_user_gets_blended_score_not_pure_popularity():
    hybrid = _build_hybrid()
    scores = hybrid.score(1, ["a1", "a2", "a3"])
    # user 1 only ever read finance articles -> a1/a2 should outrank the sports one
    assert scores["a1"] > scores["a3"]
    assert scores["a2"] > scores["a3"]


def test_cold_start_user_falls_back_to_popularity():
    hybrid = _build_hybrid()
    popularity_scores = hybrid.popularity_model.score(999, ["a1", "a2", "a3"])
    hybrid_scores = hybrid.score(999, ["a1", "a2", "a3"])
    assert hybrid_scores == popularity_scores


def test_recommend_returns_sorted_top_k():
    hybrid = _build_hybrid()
    ranked = hybrid.recommend(1, ["a1", "a2", "a3"], k=2)
    assert len(ranked) == 2
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)
