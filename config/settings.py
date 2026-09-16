"""Configuration settings for Financial RAG Agent."""

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Service
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # API Keys & Models (unused unless the corresponding cloud provider is
    # actually reached — see llm_backend / llm_cloud_fallback_order below)
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    # EDINET (金融庁) disclosure API v2 -- free instant self-service signup at
    # https://api.edinet-fsa.go.jp/. Used by scripts/ingest_edinet.py to pull
    # real 有価証券報告書 filings into data/edinet_articles.json (Tier 1
    # corpus expansion for the Hybrid RRF search panel). Empty by default;
    # ingest_edinet.py fails loudly (EdinetAuthError) rather than silently
    # skipping when this is unset.
    edinet_api_key: str = Field(default_factory=lambda: os.getenv("EDINET_API_KEY", ""))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "local-dense"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # Synthesis LLM backend: "local_cli" (default) shells out to a locally
    # installed AI CLI (no API key, see local_cli_provider_order below);
    # "template" uses the deterministic rule-based sentence assembler only
    # (fast/offline — used by the test suite so CI never spawns real CLIs).
    llm_backend: str = Field(default_factory=lambda: os.getenv("LLM_BACKEND", "local_cli"))
    local_cli_provider_order: list = Field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv("LOCAL_CLI_PROVIDER_ORDER", "opencode,claude,antigravity").split(",")
            if p.strip()
        ]
    )
    local_cli_timeout_claude: int = Field(default_factory=lambda: int(os.getenv("LOCAL_CLI_TIMEOUT_CLAUDE", "60")))
    local_cli_timeout_antigravity: int = Field(
        default_factory=lambda: int(os.getenv("LOCAL_CLI_TIMEOUT_ANTIGRAVITY", "120"))
    )
    local_cli_timeout_opencode: int = Field(
        default_factory=lambda: int(os.getenv("LOCAL_CLI_TIMEOUT_OPENCODE", "240"))
    )

    @property
    def local_cli_timeouts(self) -> dict:
        return {
            "claude": self.local_cli_timeout_claude,
            "antigravity": self.local_cli_timeout_antigravity,
            "opencode": self.local_cli_timeout_opencode,
        }

    # Cloud LLM fallback (Azure OpenAI / Google Vertex AI): opt-in, tried
    # ONLY after local_cli_provider_order is exhausted — local CLI stays the
    # default, cost-free, API-key-free path (see src/llm/cli_provider.py).
    # Empty by default => behavior is unchanged unless an operator lists
    # provider names here AND supplies the matching credentials below.
    llm_cloud_fallback_order: list = Field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv("LLM_CLOUD_FALLBACK_ORDER", "").split(",")
            if p.strip()
        ]
    )
    llm_cloud_timeout: int = Field(default_factory=lambda: int(os.getenv("LLM_CLOUD_TIMEOUT", "60")))

    # Azure OpenAI (JD tech stack: Azure OpenAI Service)
    azure_openai_api_key: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", ""))
    azure_openai_endpoint: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    azure_openai_deployment: str = Field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT", ""))
    azure_openai_api_version: str = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    )

    # Google Vertex AI (JD tech stack: Google Cloud Vertex AI). Auth is via
    # Application Default Credentials (gcloud auth / service account), not
    # an API key — only project/location/model are needed here.
    vertex_project_id: str = Field(
        default_factory=lambda: os.getenv("VERTEX_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    )
    vertex_location: str = Field(default_factory=lambda: os.getenv("VERTEX_LOCATION", "asia-northeast1"))
    vertex_model: str = Field(default_factory=lambda: os.getenv("VERTEX_MODEL", "gemini-1.5-pro"))

    # Retrieval
    hybrid_bm25_weight: float = Field(default_factory=lambda: float(os.getenv("HYBRID_BM25_WEIGHT", "0.5")))
    hybrid_vector_weight: float = Field(default_factory=lambda: float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5")))
    rrf_k: int = Field(default_factory=lambda: int(os.getenv("RRF_K", "60")))
    retrieval_top_k: int = Field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "5")))

    # MCP Server & Data Source
    mcp_server_name: str = "financial-tools-server"
    mcp_server_version: str = "1.0.0"
    # Live-only: the manual snapshot/live_api switch was removed (2026-09-15).
    # Kept as a field for backward-compat with tools that still accept a
    # `mode` kwarg, but the app no longer exposes any way to change it away
    # from "live_api" — see routes.py / static/index.html.
    data_source_mode: str = Field(default_factory=lambda: os.getenv("DATA_SOURCE_MODE", "live_api"))

    # Citation & Verification
    citation_min_confidence: float = Field(default_factory=lambda: float(os.getenv("CITATION_MIN_CONFIDENCE", "0.70")))
    max_verification_retries: int = Field(default_factory=lambda: int(os.getenv("MAX_VERIFICATION_RETRIES", "2")))


settings = Settings()
