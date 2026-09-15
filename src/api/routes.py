"""FastAPI Route Handlers with SSE Streaming and Sync execution."""

import asyncio
import json
import time
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.models.state import ChatRequest, ChatResponse
from src.graph.workflow import financial_graph
from src.graph.nodes.hybrid_search import get_shared_retriever

router = APIRouter(prefix="/api/v1", tags=["financial-rag"])


@router.get("/health")
async def health_check():
    retriever = get_shared_retriever()
    return {
        "status": "healthy",
        "service": "financial-rag-agent",
        "indexed_documents": len(retriever.documents),
        "mcp_server": "active",
        "timestamp": time.time(),
    }


@router.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Synchronous chat endpoint executing full LangGraph workflow."""
    start_time = time.time()
    session_id = request.session_id or f"session-{int(time.time())}"

    initial_state = {
        "session_id": session_id,
        "query": request.query,
        "rewritten_query": "",
        "target_tickers": [],
        "intent": "general",
        "retrieved_chunks": [],
        "financial_metrics": [],
        "draft_response": "",
        "final_response": "",
        "citations": [],
        "audit_report": None,
        "citation_consistency_score": 0.0,
        "verification_passed": False,
        "retry_count": 0,
        "execution_trace": [],
        "error": None,
    }

    config = {"configurable": {"thread_id": session_id}}
    result = await financial_graph.ainvoke(initial_state, config=config)

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return ChatResponse(
        session_id=session_id,
        query=request.query,
        rewritten_query=result.get("rewritten_query", ""),
        target_tickers=result.get("target_tickers", []),
        intent=result.get("intent", "general"),
        answer=result.get("final_response", ""),
        retrieved_chunks=result.get("retrieved_chunks", []),
        financial_metrics=result.get("financial_metrics", []),
        audit_report=result.get("audit_report", {}),
        execution_time_ms=elapsed_ms,
        execution_trace=result.get("execution_trace", []),
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Server-Sent Events (SSE) streaming endpoint emitting intermediate agent states."""
    session_id = request.session_id or f"stream-{int(time.time())}"

    async def event_generator() -> AsyncGenerator[dict, None]:
        start_time = time.time()

        yield {
            "event": "session_start",
            "data": json.dumps({"session_id": session_id, "query": request.query}),
        }
        await asyncio.sleep(0.01)

        initial_state = {
            "session_id": session_id,
            "query": request.query,
            "rewritten_query": "",
            "target_tickers": [],
            "intent": "general",
            "retrieved_chunks": [],
            "financial_metrics": [],
            "draft_response": "",
            "final_response": "",
            "citations": [],
            "audit_report": None,
            "citation_consistency_score": 0.0,
            "verification_passed": False,
            "retry_count": 0,
            "execution_trace": [],
            "error": None,
        }

        config = {"configurable": {"thread_id": session_id}}

        # Stream node-by-node updates from LangGraph
        async for output in financial_graph.astream(initial_state, config=config):
            for node_name, node_state in output.items():
                if node_name == "query_rewriter":
                    yield {
                        "event": "query_analysis",
                        "data": json.dumps({
                            "node": node_name,
                            "intent": node_state.get("intent"),
                            "target_tickers": node_state.get("target_tickers"),
                            "rewritten_query": node_state.get("rewritten_query"),
                        }, ensure_ascii=False),
                    }
                elif node_name == "hybrid_search":
                    chunks = node_state.get("retrieved_chunks", [])
                    yield {
                        "event": "retrieval_done",
                        "data": json.dumps({
                            "node": node_name,
                            "chunks_count": len(chunks),
                            "top_chunks": [{"id": c["id"], "title": c["title"], "rrf_score": c["rrf_score"]} for c in chunks[:3]],
                        }, ensure_ascii=False),
                    }
                elif node_name == "mcp_tool_runner":
                    metrics = node_state.get("financial_metrics", [])
                    yield {
                        "event": "mcp_tools_done",
                        "data": json.dumps({
                            "node": node_name,
                            "metrics_count": len(metrics),
                        }, ensure_ascii=False),
                    }
                elif node_name == "synthesizer":
                    draft = node_state.get("draft_response", "")
                    # Stream tokens in small chunks
                    chunk_size = 30
                    for i in range(0, len(draft), chunk_size):
                        yield {
                            "event": "token",
                            "data": json.dumps({"delta": draft[i:i+chunk_size]}, ensure_ascii=False),
                        }
                        await asyncio.sleep(0.01)
                elif node_name == "citation_verifier":
                    report = node_state.get("audit_report", {})
                    yield {
                        "event": "citation_audit",
                        "data": json.dumps({
                            "verdict": report.get("verdict"),
                            "consistency_rate": report.get("attribution_consistency_rate"),
                            "precision": report.get("citation_precision"),
                            "recall": report.get("citation_recall"),
                            "verified_citations": report.get("verified_citations"),
                        }, ensure_ascii=False),
                    }

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        yield {
            "event": "done",
            "data": json.dumps({"session_id": session_id, "duration_ms": elapsed_ms}),
        }

    return EventSourceResponse(event_generator())
