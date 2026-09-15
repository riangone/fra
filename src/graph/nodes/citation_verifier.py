"""Citation Verification and Audit Node."""

import time
from typing import Dict, Any
from src.models.state import AgentState
from src.citation.verifier import CitationConsistencyVerifier
from config.settings import settings


def citation_verifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Audits every sentence in the synthesized draft against retrieved source chunks
    and financial metrics. Ensures attribution consistency and detects hallucinations.
    """
    start_time = time.time()
    verifier = CitationConsistencyVerifier(min_confidence_threshold=settings.citation_min_confidence)

    draft = state.get("draft_response", "")
    chunks = state.get("retrieved_chunks", [])
    metrics = state.get("financial_metrics", [])

    report = verifier.audit_text(
        text=draft,
        retrieved_chunks=chunks,
        financial_metrics=metrics,
    )

    passed = (report.verdict == "PASS")
    retry_count = state.get("retry_count", 0)

    trace = state.get("execution_trace", [])
    trace.append({
        "node": "citation_verifier",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "verdict": report.verdict,
        "consistency_rate": report.attribution_consistency_rate,
        "precision": report.citation_precision,
        "recall": report.citation_recall,
        "verified_citations": report.verified_citations,
        "unverified_citations": report.unverified_citations,
    })

    return {
        "audit_report": report.model_dump(),
        "citation_consistency_score": report.attribution_consistency_rate,
        "verification_passed": passed,
        "retry_count": retry_count + (0 if passed else 1),
        "execution_trace": trace,
    }
