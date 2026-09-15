"""Hybrid Search Node with BM25 + Dense + RRF."""

import time
from pathlib import Path
from typing import Dict, Any
from src.models.state import AgentState
from src.retrieval.hybrid_retriever import HybridRetriever
from config.settings import settings

_retriever_instance: HybridRetriever = None


def get_shared_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
        data_path = Path(__file__).resolve().parents[3] / "data" / "sample_articles.json"
        if data_path.exists():
            _retriever_instance.load_documents_from_file(data_path)
    return _retriever_instance


def hybrid_search_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves relevant corporate documents using BM25, Dense Vector, and RRF Fusion."""
    start_time = time.time()
    retriever = get_shared_retriever()

    query_to_search = state.get("rewritten_query") or state.get("query", "")
    top_k = settings.retrieval_top_k

    # Perform hybrid search
    results = retriever.search(query=query_to_search, top_k=top_k, rrf_k=settings.rrf_k)
    chunks = [r.model_dump() for r in results]

    trace = state.get("execution_trace", [])
    trace.append({
        "node": "hybrid_search",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "chunks_retrieved": len(chunks),
        "top_chunk_id": chunks[0]["id"] if chunks else None,
        "top_rrf_score": chunks[0]["rrf_score"] if chunks else 0.0,
    })

    return {
        "retrieved_chunks": chunks,
        "execution_trace": trace,
    }
