"""Configuration settings for Financial RAG Agent."""

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Service
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # API Keys & Models (unused by default — see llm_backend below)
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
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
            for p in os.getenv("LOCAL_CLI_PROVIDER_ORDER", "claude,antigravity,opencode").split(",")
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
