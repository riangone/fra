# 金融特化型 RAG & 引用一致率監査エージェント 利用マニュアル・運用手順書 (Operations & User Manual)

## 1. はじめに

本書は、金融特化型 RAG & 引用一致率監査エージェント（`financial-rag-agent`）のセットアップ、運用保守、Web コンソール操作、API 連携、およびバッチジョブ実行に関する包括的な手順書です。

### 1.1 システム本番稼働環境
- **公開 Web Showcase 演示コンソール**: [`https://f.0101.click/`](https://f.0101.click/)
- **API ドキュメント (Swagger UI)**: [`https://f.0101.click/docs`](https://f.0101.click/docs)
- **内部サービス待受**: `127.0.0.1:8800` (FastAPI / Uvicorn)
- **リバースプロキシ**: Caddy v2 (自動 Let's Encrypt SSL / HTTP/2 / SSE ストリーミング無遅延転送)
- **常駐管理**: systemd サービス (`financial-rag-agent.service`)

---

## 2. 環境構築とセットアップ

### 2.1 必要要件
- OS: Linux (Ubuntu 22.04 LTS 以降推奨)
- Python: 3.11 または 3.12
- ネットワーク: yfinance 経由で市場データを取得する場合、外部 HTTPS 接続が必要

### 2.2 リポジトリと仮想環境の準備
```bash
# 1. プロジェクトディレクトリへ移動
cd /home/ubuntu/ws/financial-rag-agent

# 2. 仮想環境の作成 (存在しない場合)
python3 -m venv .venv

# 3. 仮想環境の有効化
source .venv/bin/activate

# 4. 依存パッケージのインストール
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.3 環境変数の設定 (`.env`)
プロジェクトルートの `.env.example` をコピーして `.env` を作成します：
```bash
cp .env.example .env
```
主要な設定項目（`config/settings.py` に対応）：
```ini
# 基本動作設定
APP_NAME=financial-rag-agent
DEBUG=false
HOST=127.0.0.1
PORT=8800

# データソース初期モード: "snapshot" または "live_api"
DATA_SOURCE_MODE=snapshot

# 検索パラメータ
RETRIEVAL_TOP_K=5
RRF_K=60

# 引用監査閾値
CITATION_MIN_CONSISTENCY=0.70
MAX_SYNTHESIS_RETRIES=2
```

---

## 3. 起動とプロセス管理

### 3.1 開発・検証環境での起動
フォアグラウンドでデバッグ実行する場合：
```bash
# 仮想環境を有効化
source .venv/bin/activate

# Uvicorn 開発サーバーの起動 (ホットリロード有効)
uvicorn src.api.app:app --host 127.0.0.1 --port 8800 --reload
```

ワンタイムのターミナル対話デモを実行する場合：
```bash
python demo.py
```

### 3.2 本番環境での常駐運用 (systemd)
本番環境では systemd ユニットファイルにより常駐デーモンとして管理されます。

#### ユニットファイル定義: `/etc/systemd/system/financial-rag-agent.service`
```ini
[Unit]
Description=Financial RAG & Citation Attribution Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ws/financial-rag-agent
ExecStart=/home/ubuntu/ws/financial-rag-agent/.venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8800 --workers 2
Restart=always
RestartSec=5
EnvironmentFile=-/home/ubuntu/ws/financial-rag-agent/.env

[Install]
WantedBy=multi-user.target
```

#### systemd 運用管理コマンド
```bash
# サービスの状態確認
sudo systemctl status financial-rag-agent

# サービスの再起動（コード変更反映時など）
sudo systemctl restart financial-rag-agent

# サービスの停止 / 起動
sudo systemctl stop financial-rag-agent
sudo systemctl start financial-rag-agent

# リアルタイムログの閲覧
journalctl -u financial-rag-agent -f
```

### 3.3 Caddy リバースプロキシの設定
Caddyfile（`/etc/caddy/Caddyfile`）内の設定：
```caddy
f.0101.click {
    reverse_proxy localhost:8800 {
        # SSE の打字機リアルタイムストリーミングを阻害しないようバッファリングを無効化
        flush_interval -1
    }
}
```
設定変更後の反映：
```bash
sudo caddy validate
sudo caddy reload
```

---

## 4. Web Showcase コンソールの利用ガイド

ブラウザで `https://f.0101.click/` にアクセスします。

### 4.1 画面レイアウト
1. **ヘッダーバー (Header)**:
   - システムステータス（Active / 稼働中）
   - **テーマ切替ボタン**: `☀️ ライト`（新聞・白基調） / `🌙 ダーク`（金融ターミナル黒基調）
   - **データソース切替トグル**: `📦 スナップショット` / `⚡ リアルタイムAPI`
2. **メインワークスペース (左ペイン)**:
   - **プリセット検索ボタン**: 「トヨタ自動車 (7203)」「ソニーグループ (6758)」「日銀利上げ政策」「ソフトバンクG (9984)」
   - **クエリ入力エリア**: 自由な自然言語での財務・ニュース分析質問
   - **ステートマシン進捗バー**: `Query Rewrite` → `Hybrid Search` → `MCP Tools` → `Synthesizer` → `Citation Verifier`
   - **回答ストリーミングエリア**: 引用タグ付き回答本文の打字機風リアルタイム描画
   - **引用監査スコアボード**: Consistency Rate (引用一致率)、Precision (適合率)、Recall (再現率)、判定バッジ (PASS / FAIL)
3. **インテリジェンス・サイドパネル (右ペイン)**:
   - **MCP 財務指標カード**: PER、PBR、ROE、TSR、時価総額、配当利回り
   - **バリュートラップ判定**: 低PBR企業の資本収益性評価
   - **検索引用元チャンク (Retrieved Chunks)**: RRF スコア付きの根拠記事カード

### 4.2 データソースの切り替え操作
- **`📦 スナップショット` モード**:
  2025/2026 年度の確定公表データおよび日経報道記事を参照。完全な再現性があり、CI/CD 評価ベンチマークと完全に合致する挙動を示します。
- **`⚡ リアルタイムAPI` モード**:
  バックグラウンドで `yfinance` 経由で東京証券取引所（東証）の最新気配値・時価総額・指標を取得。画面上のバッジが「⚡ Live yfinance (TTL: 300s)」に変化し、最新株価に基づいたバリュエーションを即座に計算します。

---

## 5. API 仕様と呼び出し例

### 5.1 全ストリーミング推論 (`POST /api/v1/chat/stream`)
打字機風のトークンストリーミングと、中間ステートマシンの監査イベントを受信します。

#### curl コール例
```bash
curl -N -X POST https://f.0101.click/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "トヨタ自動車の営業利益と今後のBEV戦略について教えてください",
    "data_source_mode": "live_api"
  }'
```

#### レスポンス受信形式 (SSE)
```text
event: status
data: {"step": "query_rewriting", "message": "クエリを分析・最適化しています..."}

event: intermediate
data: {"ticker": "7203", "mcp_data": {"ticker": "7203", "pbr": 1.12, "roe": 14.5, "per": 10.2}}

event: token
data: {"token": "ト"}

event: token
data: {"token": "ヨ"}

...

event: citation_report
data: {"consistency_rate": 0.933, "precision": 0.933, "recall": 0.812, "status": "PASS"}

event: done
data: {"status": "success", "duration_ms": 32.1}
```

### 5.2 同期推論 (`POST /api/v1/chat/sync`)
単一の JSON レスポンスで分析結果と引用監査レポートを一括取得します。
```bash
curl -X POST https://f.0101.click/api/v1/chat/sync \
  -H "Content-Type: application/json" \
  -d '{
    "query": "日銀の追加利上げ方針と為替への影響は？",
    "data_source_mode": "snapshot"
  }'
```

### 5.3 データソース動的変更 (`POST /api/v1/settings`)
サービスを再起動することなく、グローバルなデータソース設定をホットリロードします。
```bash
# リアルタイムモードへ変更
curl -X POST https://f.0101.click/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"data_source_mode": "live_api"}'

# 設定状況の確認
curl -s https://f.0101.click/api/v1/settings
```

### 5.4 ヘルスチェック (`GET /api/v1/health`)
```bash
curl -s https://f.0101.click/api/v1/health
# {"status":"healthy","service":"financial-rag-agent","indexed_documents":8,"mcp_server":"active"}
```

---

## 6. バッチ処理の実行手順

日経等の法人向けサービスにおいて、東証大引け（15:00）後の適時開示ラッシュを一括処理する深夜非同期バッチです。

### 6.1 手動実行
```bash
cd /home/ubuntu/ws/financial-rag-agent
source .venv/bin/activate

# 夜間適時開示バッチの実行
python -m src.batch.nightly_disclosure_batch
```
- **引数オプション**:
  - `--concurrency 4`: 同時並行処理ワーカー数（デフォルト: 4）
  - `--mode live_api`: 最新市場データを取得してサマリーを作成
  - `--output-dir ./reports`: レポート保存先ディレクトリ

### 6.2 cron による定期自動実行の登録例
毎日 17:30（市場開示の集約完了後）に自動実行する場合：
```cron
30 17 * * 1-5 /home/ubuntu/ws/financial-rag-agent/.venv/bin/python -m src.batch.nightly_disclosure_batch >> /home/ubuntu/ws/financial-rag-agent/batch.log 2>&1
```

---

## 7. 評価（Eval）と自動回帰テストの実行方法

### 7.1 CI/CD 向け自動評価ベンチマーク
ゴールドスタンダード評価データセット（`data/golden_eval_dataset.json`）に対する自動適合率・再現率・引用一致率の測定：
```bash
python eval/run_eval.py
```
**合格判定基準**:
- 検索 Hit Rate@3: 100%
- 引用一致率 (Consistency Rate): >= 90.0%
- 平均処理レイテンシ: < 100ms

### 7.2 ユニットおよび統合テストスイート
全 18 件のテストを実行：
```bash
pytest -v
```

---

## 8. トラブルシューティング & FAQ

### Q1. Web 画面で「接続エラー」やレスポンスの停止が発生する
- **確認手順**:
  1. `systemctl status financial-rag-agent` でバックエンドが稼働中か確認。
  2. `journalctl -u financial-rag-agent -n 50` で例外ログを確認。
  3. Caddy が正常にリバースプロキシしているか確認（`sudo systemctl status caddy`）。

### Q2. リアルタイム API モードで指標の取得が遅い／失敗する
- **原因と挙動**:
  Yahoo Finance 等の外部 API でレートリミットや一時的なネットワーク遅延が発生している可能性があります。
- **システムの自動防御**:
  本システムは 300 秒のメモリキャッシュ機構を備えており、外部 API からのエラー時には自動的にローカルの 2025/2026 スナップショットへ無停止フォールバックします。

### Q3. 引用一致率（Consistency Rate）が低下した場合の挙動
- **システムの自動自己修正**:
  LangGraph の `should_retry` エッジ判定により、一致率が 70% を下回った場合は最大 2 回まで自動的にシンセシス処理へロールバックし、より厳格な引用プロンプトで再生成を試みます。
