# financial-rag-agent 公式ドキュメント体系 (Documentation Index)

本リポジトリ（`financial-rag-agent`）は、日本経済新聞社（Nikkei）をはじめとする金融・経済メディアや金融機関のエンタープライズ品質基準に準拠した、**金融特化型 RAG & 引用一致率監査エージェント**です。

開発者、運用担当者、アーキテクト、および初学者に向けて、目的に応じた 5 つの日本語公式ドキュメントおよび専用の HTML ドキュメントポータルを提供しています。

---

## 🌐 インタラクティブ Web ドキュメントポータル
ブラウザで直接閲覧できるレスポンシブな専用ドキュメントサイト（ダーク／ライトテーマ対応、Mermaid.js 図解レンダリング）：
- 📊 **[ドキュメント総合ポータル (Portal)](./index.html)**
- 📐 **[システム詳細設計書 (Design)](./design.html)**
- 🛠️ **[利用マニュアル・運用手順書 (Manual)](./user_manual.html)**
- 💡 **[前提基礎知識ガイド (Prerequisites)](./prerequisites.html)**
- 🦉 **[小学生向け物語型解説 (Story)](./kids_guide.html)**

---

## 📚 マークダウン・ドキュメント一覧

| ドキュメント | 対象読者 | 主な内容 | リンク |
| :--- | :--- | :--- | :--- |
| **システム詳細設計書** | システムアーキテクト<br>シニアLLMエンジニア<br>技術採用担当者 | ・システム全体アーキテクチャ（Mermaid構成図）<br>・LangGraph マルチステップ状態遷移グラフ設計<br>・Model Context Protocol (MCP) 独立ツール仕様<br>・ハイブリッド検索（BM25 + Dense + RRF）数理モデル、Elasticsearch / GCP Discovery Engine 適配<br>・ローカル CLI 優先・Azure OpenAI / Vertex AI opt-in 兜底の LLM Provider フォールバック戦略<br>・文単位引用一致率（Consistency Rate）監査アルゴリズム<br>・FastAPI + SSE ストリーミングおよび非同期バッチ設計<br>・Datadog APM / W3C 準拠テレメトリ | [`DESIGN_JA.md`](./DESIGN_JA.md) |
| **利用マニュアル・運用手順書** | 運用管理者<br>サービス開発者<br>一般利用者 | ・公開環境稼働情報（`https://f.0101.click/`）<br>・環境構築（venv, requirements.txt, .env）手順<br>・起動管理（Uvicorn 開発起動 & systemd 本番常駐）<br>・Web Showcase コンソール操作法（テーマ・データソース切替・3タブ Evidence 面板）<br>・API 連携仕様（SSE ストリーミング / REST 同期）<br>・深夜非同期適時開示バッチの実行と cron 登録<br>・CI/CD 自動回帰ベンチマーク（`run_eval.py`）とテスト全 53 件実行手順<br>・障害時トラブルシューティングと FAQ | [`USER_MANUAL_JA.md`](./USER_MANUAL_JA.md) |
| **前提基礎知識ガイド** | 金融エンジニア<br>RAG / AI エンジニア | ・金融実務における RAG の固有課題とゼロハルシネーション原則<br>・従来の Linear Chain と LangGraph 状態マシンの本質的相違<br>・Model Context Protocol (MCP) 標準化動向と設計思想<br>・情報検索の基礎（BM25, Dense Vector, CJK 形態素, RRF）<br>・引用帰属（Attribution）と評価指標（Precision / Recall / 一致率）<br>・財務諸表と投資指標（PER, PBR 1倍割れ問題, ROE, TSR, バリュートラップ） | [`PREREQUISITES_JA.md`](./PREREQUISITES_JA.md) |
| **小学生でもわかる！<br>金融AIきしゃのぼうけん** | 小学生・一般初学者<br>非技術系ビジネス職 | ・小学5年生ハルキくんとAI記者「ハイペリオン」の物語<br>・株や決算（会社のつうちひょう）のやさしい解説<br>・名探偵のふたつの虫眼鏡（BM25 警察犬 ＋ ワシの目ベクトル）<br>・秘密の電卓ツール箱（MCP）<br>・ウソつき絶対見破りカメラ（鬼編集長による引用チェック）<br>・深夜に働くこびとたち（自動バッチ処理） | [`KIDS_GUIDE_JA.md`](./KIDS_GUIDE_JA.md) |
| **クラウドネイティブインフラ設計 & IaC** | SRE / プラットフォームエンジニア<br>クラウドアーキテクト | ・AWS Lambda (LWA) 预置并发冷启动排除<br>・GCP Vertex AI & Discovery Engine (1億本記事コーパス検索)<br>・Datadog APM 引用一致率 SLO & E2E レイテンシ監視<br>・Terraform IaC & Docker Compose 構成 | [`infra/README.md`](../infra/README.md) |

---

## 🌐 稼働環境リンク
- **Web Showcase コンソール**: [https://f.0101.click/](https://f.0101.click/)
- **API ドキュメント (Swagger UI)**: [https://f.0101.click/docs](https://f.0101.click/docs)
- **ヘルスチェック**: [https://f.0101.click/api/v1/health](https://f.0101.click/api/v1/health)
