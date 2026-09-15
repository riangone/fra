"""Document and Citation Data Models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    title: str
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    source: str
    date: str
    category: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    id: str
    title: str
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    source: str
    content: str
    bm25_score: float = 0.0
    dense_score: float = 0.0
    rrf_score: float = 0.0
    rank: int = 0


class CitationMarker(BaseModel):
    sentence_idx: int
    sentence_text: str
    cited_chunk_ids: List[str]
    supporting_chunk_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    is_hallucination: bool = False
    evidence_snippets: List[str] = Field(default_factory=list)


class CitationAuditReport(BaseModel):
    total_sentences: int = 0
    cited_sentences: int = 0
    verified_citations: int = 0
    unverified_citations: int = 0
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    attribution_consistency_rate: float = 0.0
    markers: List[CitationMarker] = Field(default_factory=list)
    verdict: str = "PASS"  # PASS, REVISE, FAIL
