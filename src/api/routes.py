"""FastAPI Route Handlers with SSE Streaming and Sync execution."""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.models.state import ChatRequest, ChatResponse
from src.graph.workflow import financial_graph
from src.graph.nodes.hybrid_search import get_shared_retriever
from config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["financial-rag"])


class SettingsUpdateRequest(BaseModel):
    data_source_mode: str = Field(..., description="Data source mode: 'snapshot' or 'live_api'")


@router.get("/health")
async def health_check():
    retriever = get_shared_retriever()
    return {
        "status": "healthy",
        "service": "financial-rag-agent",
        "indexed_documents": len(retriever.documents),
        "mcp_server": "active",
        "data_source_mode": settings.data_source_mode,
        "timestamp": time.time(),
    }


@router.get("/settings")
async def get_settings():
    return {
        "data_source_mode": settings.data_source_mode,
        "available_modes": [
            {
                "id": "snapshot",
                "label": "最新スナップショット (Snapshot 2025/2026)",
                "badge": "📦 SNAPSHOT",
                "description": "東証・日経確定値基盤。高速・再現性100%・CI/CD評価保証",
            },
            {
                "id": "live_api",
                "label": "リアルタイム金融API (Live yfinance)",
                "badge": "⚡ LIVE API",
                "description": "東京証券取引所(.T)・為替(USD/JPY)・日経225のリアルタイム取得",
            },
        ],
    }


@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    if req.data_source_mode not in ["snapshot", "live_api"]:
        raise HTTPException(status_code=400, detail="Invalid data_source_mode. Choose 'snapshot' or 'live_api'.")
    settings.data_source_mode = req.data_source_mode
    return {
        "status": "success",
        "data_source_mode": settings.data_source_mode,
        "message": f"Data source mode switched to '{settings.data_source_mode}'",
    }


@router.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Synchronous chat endpoint executing full LangGraph workflow."""
    start_time = time.time()
    session_id = request.session_id or f"session-{int(time.time())}"
    mode = request.data_source_mode or settings.data_source_mode

    initial_state = {
        "session_id": session_id,
        "query": request.query,
        "data_source_mode": mode,
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
    mode = request.data_source_mode or settings.data_source_mode

    async def event_generator() -> AsyncGenerator[dict, None]:
        start_time = time.time()

        yield {
            "event": "session_start",
            "data": json.dumps({
                "session_id": session_id,
                "query": request.query,
                "data_source_mode": mode,
            }, ensure_ascii=False),
        }
        await asyncio.sleep(0.01)

        initial_state = {
            "session_id": session_id,
            "query": request.query,
            "data_source_mode": mode,
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
                            "data_source_mode": mode,
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
                            "data_source_mode": mode,
                            "metrics_count": len(metrics),
                            "metrics": metrics,
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
            "data": json.dumps({
                "session_id": session_id,
                "duration_ms": elapsed_ms,
                "data_source_mode": mode,
            }, ensure_ascii=False),
        }

    return EventSourceResponse(event_generator())
