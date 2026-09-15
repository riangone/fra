"""Configuration settings for Financial RAG Agent."""

import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Service
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # API Keys & Models
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "local-dense"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # Retrieval
    hybrid_bm25_weight: float = Field(default_factory=lambda: float(os.getenv("HYBRID_BM25_WEIGHT", "0.5")))
    hybrid_vector_weight: float = Field(default_factory=lambda: float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5")))
    rrf_k: int = Field(default_factory=lambda: int(os.getenv("RRF_K", "60")))
    retrieval_top_k: int = Field(default_factory=lambda: int(os.getenv("RETRIEVAL_TOP_K", "5")))

    # MCP Server & Data Source
    mcp_server_name: str = "financial-tools-server"
    mcp_server_version: str = "1.0.0"
    data_source_mode: str = Field(default_factory=lambda: os.getenv("DATA_SOURCE_MODE", "snapshot"))  # "snapshot" or "live_api"

    # Citation & Verification
    citation_min_confidence: float = Field(default_factory=lambda: float(os.getenv("CITATION_MIN_CONFIDENCE", "0.70")))
    max_verification_retries: int = Field(default_factory=lambda: int(os.getenv("MAX_VERIFICATION_RETRIES", "2")))


settings = Settings()
