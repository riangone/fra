# news-recommender-mlops

日経の求人票（生成AI / MLエンジニア — コンテンツ推薦システム・MLOps基盤）に沿って作った、
面接・ポートフォリオ用の**独立したデモプロジェクト**です。親リポジトリの
`financial-rag-agent`（RAG × LangGraph × ハイブリッド検索）とはコードを共有せず、
同じ「金融ニュース」ドメインを題材に、求人票のもう半分＝**推薦システム設計・開発・運用**と
**MLOps設計構築**を実装で示すことを目的にしています。

## この求人票の要件とコードの対応表

| 求人票の要件 | このリポジトリでの実装 |
|---|---|
| 生成AI機能開発・周辺システム/基盤構築 | 親リポジトリ `financial-rag-agent`（RAG, LangGraph, MCP） |
| コンテンツ推薦システムのモデル設計・開発・運用 | `src/newsreco/models/`（content-based / collaborative / hybrid / popularity） |
| データ分析に基づく推薦ロジックの効果検証 | `src/newsreco/evaluation/ab_test.py`（有意差検定・信頼区間） |
| データ収集〜前処理〜学習〜デプロイのパイプライン構築 | `src/newsreco/ingestion/`, `src/newsreco/features/`, `src/newsreco/mlops/pipeline.py` |
| MLOpsの設計・構築 | `src/newsreco/mlops/`（registry / promotion gate / drift monitoring） |
| 統計検定の基礎知識 | `evaluation/ab_test.py`（Welch's t-test + bootstrap CI） |
| サービスとしての実運用経験（企画〜評価） | `serving/api.py`（FastAPI 推薦API）+ オフライン評価レポート |

## アーキテクチャ

```
                ┌─────────────────────────────────────────────┐
                │              MLOps パイプライン                │
                │  ingestion → features → train → evaluate     │
                │      → A/Bテスト → registry(昇格判定) → monitor│
                └───────────────────────┬───────────────────────┘
                                         │ artifacts/*/production.json
                                         ▼
   ユーザー要求 ──▶ FastAPI (/recommend/{user_id}) ──▶ HybridRecommender
                                         │                 ├── ContentBased (TF-IDF cosine)
                                         │                 ├── Collaborative (SVD on implicit feedback)
                                         │                 └── Popularity (cold-start fallback)
                                         ▼
                              /events でフィードバック収集
                                         │
                                         ▼
                          monitoring.py が特徴量ドリフト(PSI)を継続監視
```

### モデル構成

- **PopularityRecommender**: カテゴリ内人気度＋直近性で決まるベースライン。コールドスタート（新規ユーザー）のフォールバック。
- **ContentBasedRecommender**: 記事本文を TF-IDF ベクトル化し、ユーザーが過去に読んだ記事とのコサイン類似度でスコアリング。
- **CollaborativeRecommender**: ユーザー×記事の暗黙的フィードバック行列に対して Truncated SVD（行列分解）で潜在因子を学習。
- **HybridRecommender**: 上記3モデルの重み付き線形結合。重みはオフライン評価（NDCG@10）でチューニング。

### MLOps コンポーネント

- **registry.py**: 学習run毎にモデルとメトリクスを `artifacts/<model_name>/<version>/` にバージョニング保存。
  現行 production のメトリクスに対し、新バージョンが指定の閾値以上改善した場合のみ **昇格ゲート** を通過して
  `production.json` を更新する（勝手にモデルが入れ替わらないようにするための安全装置）。
- **pipeline.py**: データ取り込みから昇格判定・監視チェックまでを1コマンドで実行するオーケストレーター。
- **monitoring.py**: 学習時の特徴量分布と本番投入後の分布の差を **PSI (Population Stability Index)** で検知し、
  閾値を超えたら `artifacts/monitoring/drift_log.jsonl` にアラートを記録する。

## セットアップ

```bash
cd news-recommender-mlops
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) 合成データ生成（親リポジトリの実記事8件 + テンプレート合成記事、疑似ユーザー行動ログ）
python scripts/generate_synthetic_data.py

# 2) MLOpsパイプライン一括実行（学習・評価・A/Bテスト・昇格判定・ドリフト監視）
python scripts/run_pipeline.py

# 3) 推薦APIを起動
uvicorn newsreco.serving.api:app --reload --port 8001 --app-dir src
```

```bash
curl localhost:8001/health
curl localhost:8001/model/info
curl "localhost:8001/recommend/42?k=5"
curl -X POST localhost:8001/events -H 'content-type: application/json' \
     -d '{"user_id": 42, "article_id": "doc_nikkei_7203_01", "event_type": "click"}'
```

## テスト

```bash
pytest tests -v
```

## ディレクトリ構成

```
news-recommender-mlops/
├── src/newsreco/
│   ├── ingestion/        # データ読み込み・記事/行動ログの正規化
│   ├── features/         # TF-IDF・インタラクション行列の特徴量構築
│   ├── models/           # popularity / content-based / collaborative / hybrid
│   ├── evaluation/        # precision/recall/NDCG/MRR, A/Bテスト（統計検定）
│   ├── mlops/            # registry（バージョニング＋昇格ゲート）, pipeline, monitoring
│   └── serving/          # FastAPI 推薦API
├── scripts/              # 合成データ生成 / パイプライン実行CLI
├── tests/                # pytest（モデル・評価指標・MLOpsロジック・APIの単体テスト）
└── artifacts/            # 学習成果物（モデル・メトリクス・監視ログ）※ gitignore対象
```

## 設計上の割り切り（デモである旨の明記）

- ベクトル検索やLLM埋め込みではなく **TF-IDF** を採用（外部API不要・再現性重視・面接で仕組みを即座に説明できる粒度）。
  本番相当にするなら親リポジトリの `src/retrieval/embeddings.py` 系のembeddingに差し替え可能な設計にしている
  （`ContentBasedRecommender` はベクトライザをDIできる）。
- 協調フィルタリングは `implicit`/`Spark ALS` ではなく `scikit-learn` の `TruncatedSVD` で実装（依存を軽量に保つため）。
  インターフェースは差し替え可能なので、データ量が増えた際は ALS 実装に置き換えられる。
- モデルレジストリはS3/MLflowではなくローカルファイルシステム（JSON + joblib）。概念（バージョニング／昇格ゲート／メタデータ）
  はMLflow Model Registryと同型なので、そのまま置き換え可能。
