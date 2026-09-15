# Financial RAG & Citation Attribution Agent (金融特化型 RAG & 引用一致率監査エージェント)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-green.svg)](https://modelcontextprotocol.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI%20%2B%20SSE-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-38%20Passed%20(100%25)-brightgreen.svg)]()

> **Production-grade Reference Architecture for Enterprise Financial Intelligence & News Attribution**  
> 严肃金融与商业资讯场景的企业级 RAG 与多步 Agent 引擎。针对日本经济新闻社（Nikkei）等顶级财经媒体与金融机构的生产级要求设计，解决**多步复杂调度、混合检索、精准句子级引用归因（Citation Attribution）、自动化评测（Eval）与 SSE 实时流式传输**。

---

### 📖 日本語公式ドキュメント体系 (Japanese Documentation Suite)
- 📐 **[システム詳細設計書 (System Design Document)](docs/DESIGN_JA.md)**：アーキテクチャ詳細、LangGraph 状態マシン、MCP 設計、RRF 数理モデル、引用一致率監査アルゴリズム。
- 🛠️ **[利用マニュアル・運用手順書 (Operations & User Manual)](docs/USER_MANUAL_JA.md)**：環境構築、systemd 本番常駐、Web UI 操作、API 仕様、夜間バッチ、CI/CD Eval 実行。
- 💡 **[前提基礎知識ガイド (Fundamental Concepts Guide)](docs/PREREQUISITES_JA.md)**：金融×RAG の固有課題、LangGraph、MCP プロトコル標準、検索数理（BM25/Dense/RRF）、財務工学（PER/PBR/ROE/TSR/バリュートラップ）。
- 🦉 **[小学生でもわかる！金融AIきしゃのぼうけん (Story for Everyone)](docs/KIDS_GUIDE_JA.md)**：ハルキくんとAI記者ハイペリオンの冒険物語で学ぶ金融AIのしくみ。
- ☁️ **[クラウドネイティブインフラ設計 & IaC (Cloud-Native Infrastructure)](infra/README.md)**：AWS Lambda (LWA) + GCP Discovery Engine / Vertex AI + Datadog APM 監視設計書。
- 📑 **[ドキュメント総合目次 (Documentation Index)](docs/README.md)**

---

## 🏗️ 系统架构设计 (System Architecture)

```mermaid
flowchart TD
    User["User Query / API Client"] --> FastAPI["FastAPI Gateway (SSE / REST)"]
    FastAPI --> LG["LangGraph StateGraph Engine"]
    
    subgraph LG_Flow ["LangGraph Multi-Step Orchestration"]
        QR["1. Query Rewriter & Intent Classifier"]
        HS["2. Hybrid Search (BM25 + Dense + RRF)"]
        MCP_Node["3. MCP Financial Tool Invocation"]
        SYN["4. Grounded Citation Synthesizer"]
        VER["5. Citation Attribution & Consistency Verifier"]
        
        QR --> HS
        HS --> MCP_Node
        MCP_Node --> SYN
        SYN --> VER
        VER -->|"Consistency < 70% (Retry)"| SYN
        VER -->|"Verified (PASS)"| DONE["State Checkpointer (MemorySaver)"]
    end
    
    HS <--> Corpus[("Nikkei & JPX Filings Corpus")]
    MCP_Node <--> MCPServer["MCP Financial Server\n(PER/PBR/ROE/TSR/Disclosures)"]
    VER --> Audit["Attribution Audit Report\n(Precision, Recall, 引用一致率)"]
    DONE --> SSE["SSE Real-time Stream\n(Tokens + Intermediate Audit Events)"]
    SSE --> User
```

---

## 🎯 核心技术亮点与能力对应 (Core Architectural Pillars)

| 日经 (Nikkei) JD 岗位核心诉求 | 本项目（financial-rag-agent）核心实现 | 模块路径 |
| :--- | :--- | :--- |
| **LangGraph 复杂多步工作流** | 基于 `StateGraph` 的状态机控制、多轮改写、Intent 分类、持久化 Checkpointer、循环自修正 Edge。 | [`src/graph/workflow.py`](file:///home/ubuntu/ws/financial-rag-agent/src/graph/workflow.py) |
| **Model Context Protocol (MCP)** | 遵循标准 MCP 协议，构建独立的 Financial Tools 模块，输出 PER/PBR/ROE/TSR 估值指标与 JPX 决算披露。 | [`src/mcp_server/server.py`](file:///home/ubuntu/ws/financial-rag-agent/src/mcp_server/server.py) |
| **混合检索 (Hybrid Retrieval) & RRF** | CJK 双字切词与复合金融数值解析 + BM25 Okapi + Dense Vector Cosine Similarity + Reciprocal Rank Fusion (RRF)。 | [`src/retrieval/hybrid_retriever.py`](file:///home/ubuntu/ws/financial-rag-agent/src/retrieval/hybrid_retriever.py) |
| **大规模搜索引擎适配 (Elasticsearch)** | Elasticsearch 8.x Kuromoji 全文检索 + Dense Vector KNN 向量检索适配器。 | [`src/retrieval/es_adapter.py`](file:///home/ubuntu/ws/financial-rag-agent/src/retrieval/es_adapter.py) |
| **引用管理与一致率 (Citation Attribution)** | **句子级精确引用引擎**：自动拆分句子、匹配实体与数值事实、校验 `[doc_id]` 引用一致性，杜绝金融幻觉。 | [`src/citation/verifier.py`](file:///home/ubuntu/ws/financial-rag-agent/src/citation/verifier.py) |
| **夜间非同期バッチ基盤 (Batch Pipeline)** | 针对东证大引盘后适时开示的并发受控（Semaphore）自动分析、Markdown 摘要生成与引用归因管道。 | [`src/batch/nightly_disclosure_batch.py`](file:///home/ubuntu/ws/financial-rag-agent/src/batch/nightly_disclosure_batch.py) |
| **云原生 IaC 与生产基础设施 (Multi-Cloud)** | 完整 Terraform IaC：AWS Lambda (LWA) 预置并发冷启动规避、GCP Discovery Engine / Vertex AI 与 Datadog SLO 告警。 | [`infra/`](file:///home/ubuntu/ws/financial-rag-agent/infra) |
| **分布式遥测与可观测性 (Observability)** | W3C TraceContext 跨进程链路追踪，集成 Datadog APM 规范结构化 JSON 遥测日志。 | [`src/monitoring/telemetry.py`](file:///home/ubuntu/ws/financial-rag-agent/src/monitoring/telemetry.py) |
| **自动化评测 (Eval) & CI 回归测试** | 黄金测试集基准测试：计算 HitRate@K, MRR@K, 引用一致率, 引用适合率, 引用再现率与 P95 延迟。 | [`eval/run_eval.py`](file:///home/ubuntu/ws/financial-rag-agent/eval/run_eval.py) |
| **生产级后端架构 (FastAPI + SSE)** | 异步全流式 Server-Sent Events，实时推送 Agent 思考状态、中间检索结果、Token 流与最终审计报告。 | [`src/api/routes.py`](file:///home/ubuntu/ws/financial-rag-agent/src/api/routes.py) |

---

## 📊 基准测试评估报告 (Automated Evaluation Benchmark)

运行 `python eval/run_eval.py` 对真实日本财经数据集（トヨタ 7203、ソニー 6758、ソフトバンク 9984、三菱UFJ 8306、日銀 MACRO 等）进行端到端评测：

```text
=======================================================
📊 BENCHMARK SUMMARY REPORT (Gold Standard Dataset)
=======================================================
• 検索精度 (Retrieval Metrics):
  - Hit Rate@1:               83.3%
  - Hit Rate@3:              100.0%
  - Hit Rate@5:              100.0%
  - Mean Reciprocal Rank:     0.917
• 根拠性・引用精度 (Citation Attribution Metrics):
  - 引用一致率 (Consistency):    93.3%
  - 引用適合率 (Precision):      93.3%
  - 引用再現率 (Recall):         79.5%
  - 忠実度 (Faithfulness):       70.8%
• システム性能 (Latency):
  - 平均エンドツーエンド遅延:     21.8 ms
=======================================================
```

---

## 🚀 快速启动指南 (Quickstart Guide)

### 1. 环境准备 (Environment Setup)
```bash
cd /home/ubuntu/ws/financial-rag-agent

# 使用 uv (或系统 python) 激活虚拟环境
source .venv/bin/activate

# 安装依赖（若使用现有环境已全部配置就绪）
pip install -r requirements.txt
```

### 2. 运行一键端到端 Showcase
```bash
python demo.py
```
> 执行完整的 LangGraph 状态机调用、MCP 财务数据提取、混合检索与实时引用一致率审计。

### 3. 运行自动化评测基准 (Automated Eval Benchmark)
```bash
python eval/run_eval.py
```

### 4. 运行完整单元与集成测试套件 (38 Tests)
```bash
pytest -v
```

### 5. 启动生产级 FastAPI + SSE 服务
```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8800 --reload
```
访问 API 文档：`http://localhost:8800/docs`

#### SSE 流式调用示例 (curl)
```bash
curl -N -X POST http://localhost:8800/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "トヨタ自動車の2024年3月期の営業利益とBEV投資計画について教えてください"}'
```

---

## 📂 项目工程目录 (Repository Structure)

```text
financial-rag-agent/
├── README.md                      # 本文档（中/日/英架构与评测说明）
├── docs/                          # 📖 完整日文文档体系与静态 Web 门户
│   ├── README.md                  # 文档综合目次 (Index)
│   ├── DESIGN_JA.md               # 系统详细设计书 (Architecture & Core Design)
│   ├── USER_MANUAL_JA.md          # 利用与运维手册 (Operations & User Manual)
│   ├── PREREQUISITES_JA.md        # 前提基础知识指南 (Fundamental Knowledge)
│   ├── KIDS_GUIDE_JA.md           # 小学生也能看懂的科普故事 (Story Guide)
│   ├── index.html                 # 静态文档 Portal 门户主页
│   ├── design.html                # 详细设计书 HTML 交互页面 (Mermaid/Dark/Light)
│   ├── user_manual.html           # 运维手册 HTML 交互页面
│   ├── prerequisites.html         # 基础知识指南 HTML 交互页面
│   ├── kids_guide.html            # 科普故事 HTML 交互页面
│   └── assets/                    # 文档前端样式 (docs.css) 与主题脚本 (docs.js)
├── infra/                         # ☁️ 生产级云原生与 IaC 基础设施
│   ├── README.md                  # 日经生产多云（AWS+GCP）架构说明
│   ├── docker/                    # Dockerfile (多阶段构建), Dockerfile.lambda, docker-compose.yml
│   └── terraform/                 # AWS Lambda (LWA), GCP Vertex AI / Discovery Engine, Datadog APM
├── pyproject.toml                 # 项目元数据与依赖配置
├── requirements.txt               # 生产依赖列表
├── .env.example                   # 环境变量配置模板
├── demo.py                        # 一键运行 Showcase 演示脚本
├── config/
│   └── settings.py                # Pydantic 集中配置管理
├── data/
│   ├── sample_articles.json       # 日经风格新闻与 JPX 财报开示数据
│   └── golden_eval_dataset.json   # 黄金评测基准数据集
├── src/
│   ├── models/                    # Pydantic & TypedDict 数据契约
│   │   ├── state.py               # LangGraph AgentState 与 API 协议
│   │   ├── document.py            # RetrievedChunk 与 CitationAuditReport
│   │   └── finance.py             # 估值模型 (PER/PBR/ROE/TSR/バリュートラップ)
│   ├── graph/                     # LangGraph 状态机与编排流
│   │   ├── workflow.py            # StateGraph 组装与 Checkpointer 持久化
│   │   ├── edges.py               # 条件分支与审查重试策略
│   │   └── nodes/                 # 独立节点实现 (QueryRewriter, HybridSearch, MCPToolRunner, Synthesizer, CitationVerifier)
│   ├── retrieval/                 # 检索核心算法
│   │   ├── hybrid_retriever.py    # BM25 + Dense Vector 混合检索
│   │   ├── reranker.py            # Reciprocal Rank Fusion (RRF)
│   │   ├── embeddings.py          # 稠密向量嵌入引擎
│   │   └── es_adapter.py          # Elasticsearch 8.x Kuromoji & KNN 适配器
│   ├── mcp_server/                # Model Context Protocol 标准服务
│   │   ├── server.py              # MCPServer 实现 (stdio / SSE)
│   │   ├── client.py              # 异步 MCP 客户端适配器
│   │   └── tools/                 # 财务估值、适时开示与宏观指标工具
│   ├── citation/                  # 引用与事实归因引擎
│   │   ├── extractor.py           # 句子级引用标记提取
│   │   └── verifier.py            # 事实/数值重合度与一致率校验器
│   ├── batch/                     # 🌙 夜间适时开示非同期批处理基盘
│   │   └── nightly_disclosure_batch.py # 并发受控的自律型开示分析与研报生成管道
│   ├── monitoring/                # 📊 分布式遥测与可观测性
│   │   └── telemetry.py           # W3C TraceContext 传播与 Datadog APM 结构化日志
│   ├── llm/                       # LLM Provider 与降级引擎
│   │   └── cli_provider.py        # Local CLI 快速推理与降级适配器
│   ├── api/                       # Web 服务与接口
│   │   ├── app.py                 # FastAPI 声明与生命周期
│   │   ├── routes.py              # SSE 流式 & 同步推理接口
│   │   └── static/index.html      # 金融终端前端（日经 Hybrid RAG × Live MCP 双轮驱动面板）
│   └── cli.py                     # 交互式命令行工具
├── eval/                          # 自动化评测体系
│   ├── metrics.py                 # HitRate, MRR, 引用一致率, 适合率, 再现率
│   └── run_eval.py                # 评测套件驱动程序
└── tests/                         # 自动化测试套件 (38 passed)
    ├── test_hybrid_search.py      # BM25, Vector, RRF 单元测试
    ├── test_mcp_tools.py          # MCP 工具及协议测试 (包含 Live 行情波动宽容区间校验)
    ├── test_citation_verifier.py  # 引用审计与幻觉检测测试
    ├── test_langgraph_workflow.py # LangGraph 状态流转与集成测试
    ├── test_api_sse.py            # FastAPI 与 SSE 流式接口测试
    ├── test_batch_pipeline.py     # 夜间批处理并发与管道集成测试
    ├── test_cli_provider.py       # CLI Provider 推理与降级测试
    └── test_local_cli_synthesis.py# 本地合成与引用验证回归测试
```

---

## 🔗 与现有资产的协同复用 (Ecosystem Synergy)

本项目并非孤立玩具，而是与你在 `ws` 目录下的核心技术资产深度协同互补：
- **[`stock_skills`](file:///home/ubuntu/ws/stock_skills/README.md)**：将 `stock_skills` 中经 1,500+ 测试验证的 PER/PBR/ROE 估值模型、TSR、バリュートラップ（价值陷阱）检测规则，通过标准 **MCP 协议** 对外暴露为 Agent 工具。
- **[`ai-chat-app`](file:///home/ubuntu/ws/ai-chat-app/AiChatApp/README_ZH.md)**：将原自研 DAG/Blackboard 架构无缝升级为业界标准的 **LangGraph StateGraph**。
- **[`a2a-enterprise-gateway`](file:///home/ubuntu/ws/a2a-enterprise-gateway/main.py) & [`agent-dex`](file:///home/ubuntu/ws/agent-dex/README.md)**：借鉴网关的高并发降级策略与企业级审计追踪机制，在 API 与 Trace 日志中提供完整的全链路耗时与状态快照。
