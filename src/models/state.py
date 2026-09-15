"""LangGraph State Definition and API Schemas."""

from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from src.models.document import RetrievedChunk, CitationAuditReport
from src.models.finance import FinancialMetrics


class AgentState(TypedDict):
    # User Input
    session_id: str
    query: str
    
    # Query Analysis
    rewritten_query: str
    target_tickers: List[str]
    intent: str  # 'valuation', 'earnings', 'macro', 'comparison', 'general'
    
    # Intermediate Artifacts
    retrieved_chunks: List[Dict[str, Any]]
    financial_metrics: List[Dict[str, Any]]
    
    # Synthesis & Attribution
    draft_response: str
    final_response: str
    citations: List[Dict[str, Any]]
    audit_report: Optional[Dict[str, Any]]
    
    # Control Flow & Reliability
    citation_consistency_score: float
    verification_passed: bool
    retry_count: int
    execution_trace: List[Dict[str, Any]]
    error: Optional[str]


# API Request & Response Schemas
class ChatRequest(BaseModel):
    query: str = Field(..., description="User question in natural language (Japanese or English)")
    session_id: Optional[str] = Field(default="default-session")
    force_verify: bool = Field(default=True, description="Strict citation verification enabled")


class ChatResponse(BaseModel):
    session_id: str
    query: str
    rewritten_query: str
    target_tickers: List[str]
    intent: str
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    financial_metrics: List[Dict[str, Any]] = Field(default_factory=list)
    audit_report: CitationAuditReport
    execution_time_ms: float
    execution_trace: List[Dict[str, Any]]
