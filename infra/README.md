# Cloud-Native Infrastructure & IaC (日経本番運用アーキテクチャ)

本ディレクトリは、日本経済新聞社の BtoB デジタル情報サービス（日経リスク＆コンプライアンス、NIKKEI The KNOWLEDGE、NIKKEI KAI）の運用制約を満たす、**マルチクラウド（AWS + GCP）およびサーバーレス IaC 構成**を定義します。

---

## 1. システム全体構成図 (Multi-Cloud Architecture)

```mermaid
flowchart TD
    subgraph ClientLayer ["クライアント & UI"]
        Browser["ブラウザ (Terminal UI)"]
        BatchTrigger["東証引け後トリガー (15:30 JST)"]
    end

    subgraph AWS ["AWS (東京リージョン ap-northeast-1)"]
        APIGW["Amazon API Gateway HTTP API (v2)"]
        LambdaStreaming["AWS Lambda (FastAPI + LangGraph)<br/>• Provisioned Concurrency (コールドスタート排除)<br/>• AWS Lambda Web Adapter (SSE Stream)"]
        LambdaBatch["AWS Lambda (夜間開示バッチ)<br/>• Semaphore 並行制御 (5並列)<br/>• 15分タイムアウト"]
        EventBridge["Amazon EventBridge (cron: 平日 15:30 JST)"]
        ECR["Amazon ECR (コンテナレジストリ)"]
    end

    subgraph GCP ["Google Cloud (東京リージョン asia-northeast1)"]
        DiscoveryEngine["Google Cloud Discovery Engine<br/>(1億本超の過去記事コーパス全文検索)"]
        VertexAI["Google Vertex AI<br/>(Embedding / LLM 推論)"]
        CloudRun["Cloud Run (代替コンテナ実行環境)"]
    end

    subgraph External ["データプロバイダ & 外部連携"]
        MCP["FastMCP Server (財務指標・適時開示)"]
        TSE["東証 TDnet / yfinance Live API"]
    end

    subgraph Monitoring ["可観測性 & SLO 監視"]
        Datadog["Datadog APM & Metrics<br/>• 引用一致率 SLO (< 85% アラート)<br/>• E2E レイテンシ SLO (P95 < 15s)<br/>• Synthetics 外形監視"]
    end

    Browser -->|SSE ストリーミング| APIGW
    APIGW --> LambdaStreaming
    EventBridge -->|平日定期実行| LambdaBatch
    LambdaStreaming --> DiscoveryEngine
    LambdaStreaming --> VertexAI
    LambdaStreaming --> MCP
    MCP --> TSE
    LambdaBatch --> MCP
    LambdaStreaming -.->|W3C TraceContext| Datadog
```

---

## 2. 本番運用制約への技術的対策 (Production Constraints)

### ① コールドスタート排除と応答 SLO
- **課題**: サーバーレス環境（Lambda / Cloud Run）におけるコンテナ起動時（Python ランタイム + 依存パッケージ）の初期遅延（3〜6秒）が、リアルタイム金融アナリストツールの SLO（初回レスポンス < 1.0秒）を毀損する。
- **対策**:
  - `aws_lambda_provisioned_concurrency_config` により常時 5 インスタンスを事前プロビジョニング。
  - Docker マルチステージビルド（`python:3.12-slim` + `uv`）でイメージサイズを最小化。
  - AWS Lambda Web Adapter（LWA）を採用し、FastAPI の SSE `StreamingResponse` をチャンク変換オーバーヘッドなしでネイティブ直接透過。

### ② 同時実行上限とコスト・レートリミット制御
- **課題**: 多数のユーザーが一斉にマルチステップエージェントを実行すると、LLM バックエンドの Quota 上限（TPM / RPM）に到達し、429 Too Many Requests が発生する。
- **対策**:
  - `reserved_concurrent_executions = 50` により、同時実行枠を明示的に予約・制限。
  - 夜間バッチ（`src/batch/nightly_disclosure_batch.py`）では `asyncio.Semaphore(5)` により東証銘柄の並行処理レートを自動調整。

### ③ 非同期バッチ生成基盤 (EventBridge 定期実行)
- **特徴**: ユーザー入力をトリガーとせず、平日 15:30 JST（東証大引け・適時開示集中時間）に EventBridge が `nikkei-disclosure-nightly-batch` を自動発火。大量の適時開示からサマリーレポートを自律生成し、監査済み引用付きで蓄積。

### ④ 品質保証と Datadog APM 連携
- **引用一致率 SLO**: 一致率が 85% を下回った場合に Datadog Monitor が発火。
- **レイテンシ監視**: P95 レイテンシが 15 秒を超過した場合にアラート通知。
- **W3C 分散トレーシング**: リクエストヘッダー `traceparent` を伝播し、FastAPI → LangGraph 节点 → MCP Server 間のレイテンシ内訳を完全に可視化。

---

## 3. デプロイ手順

### Terraform の適用
```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

### Docker Compose によるローカル本番シミュレーション
```bash
cd infra/docker
docker compose up --build
```
- Web UI / API: `http://localhost:8000`
- Elasticsearch (Kuromoji 8.13): `http://localhost:9200`
- FastMCP Server: `http://localhost:8001`
