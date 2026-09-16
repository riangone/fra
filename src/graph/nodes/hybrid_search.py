"""Hybrid Search Node with BM25 + Dense + RRF."""

import json
import time
from pathlib import Path
from typing import Dict, Any
from src.models.document import Document
from src.models.state import AgentState
from src.retrieval.hybrid_retriever import HybridRetriever
from config.settings import settings

_retriever_instance: HybridRetriever = None

# Loaded in this order and merged into one corpus (later files win on id
# collision). sample_articles.json is the original 8-row hand-written seed
# corpus; edinet_articles.json is the optional Tier 1 expansion produced by
# scripts/ingest_edinet.py from real EDINET (金融庁) filings -- absent by
# default, additive only, never required for the app to run.
_CORPUS_FILES = ("sample_articles.json", "edinet_articles.json")


def _load_merged_corpus(data_dir: Path) -> Dict[str, Document]:
    """Load and merge every file in _CORPUS_FILES found under `data_dir`,
    keyed by Document.id (a later file overwrites an earlier one on
    collision). Missing files are silently skipped -- only
    sample_articles.json is expected to always exist.
    """
    merged: Dict[str, Document] = {}
    for filename in _CORPUS_FILES:
        data_path = data_dir / filename
        if not data_path.exists():
            continue
        with open(data_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                doc = Document(**item)
                merged[doc.id] = doc
    return merged


def get_shared_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
        data_dir = Path(__file__).resolve().parents[3] / "data"
        merged = _load_merged_corpus(data_dir)
        if merged:
            _retriever_instance.index_documents(list(merged.values()))
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
