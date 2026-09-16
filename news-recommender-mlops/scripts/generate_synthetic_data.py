"""Generate a synthetic-but-structured dataset for the recommender demo.

Real content: the 8 hand-written Nikkei-style articles from the parent
`financial-rag-agent/data/sample_articles.json` are included as-is.

Synthetic content: additional articles are generated from category-specific
templates filled in with real TSE-listed company names/tickers
(`financial-rag-agent/data/tse_listed_companies.csv`), so the corpus has enough
volume and topical variety for TF-IDF / collaborative filtering to have signal,
without needing any external API or hand-labeled dataset.

Synthetic users: each user gets a Dirichlet-sampled "interest profile" over
categories (peaky, i.e. most users are into 2-3 topics, not all of them), which
is what creates learnable structure for the collaborative filtering model —
this mirrors how real reader cohorts cluster around beats (macro, M&A,
earnings, tech...).
"""

from __future__ import annotations

import csv
import json
import random
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
OUT_DATA = PROJECT_DIR / "data"
# Seed files are committed snapshots of financial-rag-agent/data/{sample_articles.json,
# tse_listed_companies.csv}, copied in so this project has zero runtime dependency on
# the parent repo (it started life alongside it, but stands on its own).
SEED_REAL_ARTICLES = OUT_DATA / "seed_real_articles.json"
SEED_COMPANIES = OUT_DATA / "seed_companies.csv"

RNG_SEED = 42
N_SYNTHETIC_USERS = 300
DAYS_OF_HISTORY = 60
VARIANTS_PER_TEMPLATE = 4

CATEGORY_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "決算・財務": [
        (
            "{company}、{fy}期決算は営業利益{pct}%{direction}の{yen}億円",
            "{company}（{ticker}）が発表した{fy}期の連結決算は、営業利益が前期比{pct}%{direction}の{yen}億円となった。"
            "売上高は{rev}億円で、{driver}が業績を{direction2}した。次期見通しについても市場の注目が集まっている。",
        ),
        (
            "{company}、四半期純利益が市場予想を{beat_miss}",
            "{company}（{ticker}）の直近四半期決算では、純利益が市場コンセンサスを{beat_miss}した。"
            "背景には{driver}があり、アナリストは今後の業績動向を注視している。",
        ),
    ],
    "経営戦略": [
        (
            "{company}、中期経営計画で{theme}に{yen}億円投資へ",
            "{company}（{ticker}）は新たな中期経営計画を発表し、{theme}分野に今後3年間で{yen}億円を投資する方針を示した。"
            "{driver}を成長ドライバーと位置づけ、収益構造の転換を目指す。",
        ),
    ],
    "M&A": [
        (
            "{company}、{target}を買収し{theme}事業を強化",
            "{company}（{ticker}）は{target}の株式を取得し、{theme}事業の強化に乗り出すと発表した。"
            "買収額は{yen}億円規模とみられ、{driver}を通じたシナジー創出を狙う。",
        ),
    ],
    "マクロ経済": [
        (
            "日銀、{policy}を{direction3}方針",
            "日本銀行は金融政策決定会合で{policy}について議論し、{direction3}方向で調整に入ったとみられる。"
            "{driver}を踏まえた判断で、市場では{policy}を巡る思惑が交錯している。",
        ),
    ],
    "市場・株式": [
        (
            "東京株式市場、{sector}関連株が{direction4}",
            "東京株式市場では{sector}関連銘柄が{direction4}した。{company}（{ticker}）を中心に物色が広がり、"
            "{driver}が投資家心理を左右した。",
        ),
    ],
    "技術・イノベーション": [
        (
            "{company}、{theme}分野で新技術を発表",
            "{company}（{ticker}）は{theme}分野における新技術を発表した。{driver}を背景に実用化を急ぐ構えで、"
            "業界内での競争優位確立を目指す。",
        ),
    ],
    "業績修正": [
        (
            "{company}、通期業績予想を{direction5}修正",
            "{company}（{ticker}）は通期の業績予想を{direction5}修正すると発表した。{driver}が主な要因で、"
            "修正後の営業利益は{yen}億円を見込む。",
        ),
    ],
    "資本政策": [
        (
            "{company}、自己株式取得と増配を発表",
            "{company}（{ticker}）は自己株式取得枠の設定と増配を発表した。{driver}を踏まえた株主還元強化策で、"
            "資本効率の改善を進める考えだ。",
        ),
    ],
}

THEMES = ["生成AI", "半導体", "再生可能エネルギー", "モビリティ", "ヘルスケア", "サプライチェーン", "データセンター", "脱炭素"]
DRIVERS = ["円安の進行", "海外需要の拡大", "原材料価格の高騰", "人件費の上昇", "国内消費の持ち直し", "地政学リスクの高まり", "デジタル投資の加速"]
SECTORS = ["半導体", "自動車", "銀行", "商社", "医薬品", "情報通信"]
POLICIES = ["マイナス金利政策の解除", "長短金利操作の柔軟化", "国債買い入れ額の調整", "追加利上げ"]


def load_real_articles() -> list[dict]:
    return json.loads(SEED_REAL_ARTICLES.read_text(encoding="utf-8"))


def load_companies(rng: random.Random, n: int) -> list[tuple[str, str]]:
    rows = []
    with SEED_COMPANIES.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((row["code"], row["name"]))
    return rng.sample(rows, k=min(n, len(rows)))


def render(template: str, rng: random.Random, ticker: str, company: str) -> str:
    pct = rng.randint(2, 45)
    return template.format(
        company=company,
        ticker=ticker,
        fy=f"{rng.choice(['2024年3月', '2024年12月', '2025年3月'])}",
        pct=pct,
        direction=rng.choice(["増", "減"]),
        direction2=rng.choice(["押し上げ", "下支え", "圧迫"]),
        direction3=rng.choice(["維持する", "見直す", "修正する"]),
        direction4=rng.choice(["上昇", "下落", "堅調に推移"]),
        direction5=rng.choice(["上方", "下方"]),
        yen=rng.randint(50, 8000),
        rev=rng.randint(500, 90000),
        beat_miss=rng.choice(["上回った", "下回った"]),
        driver=rng.choice(DRIVERS),
        theme=rng.choice(THEMES),
        target=f"{rng.choice(['アルファ', 'ベータ', 'ノーザン', 'サザン'])}{rng.choice(['テクノロジーズ', 'ホールディングス', 'システムズ'])}",
        policy=rng.choice(POLICIES),
        sector=rng.choice(SECTORS),
    )


def generate_synthetic_articles(rng: random.Random) -> list[dict]:
    companies = load_companies(rng, n=40)
    articles: list[dict] = []
    counter = 0
    base_date = time.time() - DAYS_OF_HISTORY * 86400

    for category, templates in CATEGORY_TEMPLATES.items():
        for title_tmpl, content_tmpl in templates:
            for _ in range(VARIANTS_PER_TEMPLATE):
                ticker, company = rng.choice(companies)
                title = render(title_tmpl, rng, ticker, company)
                content = render(content_tmpl, rng, ticker, company)
                day_offset = rng.uniform(0, DAYS_OF_HISTORY)
                article_date = base_date + day_offset * 86400
                counter += 1
                articles.append(
                    {
                        "id": f"syn_{counter:04d}",
                        "title": title,
                        "content": content,
                        "category": category,
                        "ticker": ticker,
                        "company_name": company,
                        "source": "日本経済新聞",
                        "date": time.strftime("%Y-%m-%d", time.localtime(article_date)),
                        "_ts": article_date,
                    }
                )
    return articles


def generate_users_and_interactions(
    rng: random.Random, articles: list[dict]
) -> list[dict]:
    categories = sorted({a["category"] for a in articles})
    by_category: dict[str, list[dict]] = {c: [] for c in categories}
    for a in articles:
        by_category[a["category"]].append(a)

    now = time.time()
    window_start = now - DAYS_OF_HISTORY * 86400

    interactions: list[dict] = []
    for user_id in range(1, N_SYNTHETIC_USERS + 1):
        # peaky Dirichlet -> most users concentrate on a couple of topics
        alpha = [0.3] * len(categories)
        interest = _dirichlet(rng, alpha)
        interest_by_cat = dict(zip(categories, interest))

        n_events = rng.randint(15, 80)
        for _ in range(n_events):
            category = rng.choices(categories, weights=interest, k=1)[0]
            pool = by_category[category]
            if not pool:
                continue
            article = rng.choice(pool)
            affinity = interest_by_cat[category]
            # stronger affinity -> more likely to be a deep-engagement event
            roll = rng.random()
            if roll < 0.5 * affinity * len(categories):
                event_type = rng.choice(["click", "read_long", "like"])
            else:
                event_type = "view"
            timestamp = rng.uniform(max(window_start, article["_ts"]), now)
            interactions.append(
                {
                    "user_id": user_id,
                    "article_id": article["id"],
                    "event_type": event_type,
                    "timestamp": timestamp,
                }
            )
    return interactions


def _dirichlet(rng: random.Random, alpha: list[float]) -> list[float]:
    """Dirichlet sampling without a numpy dependency (via independent Gammas)."""
    samples = [rng.gammavariate(a, 1.0) for a in alpha]
    total = sum(samples) or 1.0
    return [s / total for s in samples]


def main() -> None:
    rng = random.Random(RNG_SEED)
    OUT_DATA.mkdir(parents=True, exist_ok=True)

    real_articles = load_real_articles()
    for a in real_articles:
        a["_ts"] = time.time() - rng.uniform(0, DAYS_OF_HISTORY) * 86400
    synthetic_articles = generate_synthetic_articles(rng)
    all_articles = real_articles + synthetic_articles

    interactions = generate_users_and_interactions(rng, all_articles)

    from newsreco.ingestion.schema import EVENT_WEIGHTS  # local import: needs src on path

    articles_out = [{k: v for k, v in a.items() if k != "_ts"} for a in all_articles]
    (OUT_DATA / "articles.json").write_text(
        json.dumps(articles_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (OUT_DATA / "interactions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "article_id", "event_type", "timestamp", "weight"])
        for it in interactions:
            writer.writerow(
                [it["user_id"], it["article_id"], it["event_type"], it["timestamp"], EVENT_WEIGHTS[it["event_type"]]]
            )

    print(f"wrote {len(articles_out)} articles -> {OUT_DATA / 'articles.json'}")
    print(f"wrote {len(interactions)} interactions -> {OUT_DATA / 'interactions.csv'}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(PROJECT_DIR / "src"))
    main()
