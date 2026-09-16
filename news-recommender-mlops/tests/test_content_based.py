from newsreco.features.build_features import build_content_features
from newsreco.ingestion.schema import Article, Interaction
from newsreco.models.content_based import ContentBasedRecommender

FINANCE_ARTICLES = [
    Article(id="fin1", title="トヨタ決算", content="トヨタ自動車の営業利益は増益となった 決算 業績", category="決算・財務"),
    Article(id="fin2", title="ソニー決算", content="ソニーグループの営業利益は増益となった 決算 業績", category="決算・財務"),
]
SPORTS_ARTICLES = [
    Article(id="sport1", title="野球優勝", content="プロ野球のチームが優勝を決めた 試合 選手 スタジアム", category="スポーツ"),
    Article(id="sport2", title="サッカー勝利", content="サッカーチームが勝利し順位を上げた 試合 選手 スタジアム", category="スポーツ"),
]


def _fit_recommender(interactions):
    articles = FINANCE_ARTICLES + SPORTS_ARTICLES
    cf = build_content_features(articles)
    model = ContentBasedRecommender(cf)
    model.fit(interactions)
    return model


def test_similar_articles_finds_same_topic():
    model = _fit_recommender([])
    similar = model.similar_articles("fin1", k=3)
    top_id = similar[0][0]
    assert top_id == "fin2"  # same-topic article should rank first among candidates


def test_user_profile_scores_matching_topic_higher():
    # user only ever read finance articles
    interactions = [
        Interaction(user_id=1, article_id="fin1", event_type="click", timestamp=1.0, weight=2.0),
    ]
    model = _fit_recommender(interactions)
    scores = model.score(1, ["fin2", "sport1", "sport2"])
    assert scores["fin2"] > scores["sport1"]
    assert scores["fin2"] > scores["sport2"]


def test_unknown_user_gets_zero_scores_not_an_error():
    model = _fit_recommender([])
    scores = model.score(999, ["fin1", "sport1"])
    assert scores == {"fin1": 0.0, "sport1": 0.0}
