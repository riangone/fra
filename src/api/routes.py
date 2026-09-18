"""FastAPI Route Handlers with SSE Streaming and Sync execution."""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.models.state import ChatRequest, ChatResponse, WatchlistAddRequest
from src.graph.workflow import financial_graph
from src.graph.nodes.hybrid_search import get_shared_retriever
from src.services import watchlist as watchlist_service
from src.mcp_server.tools.live_market_client import fetch_live_stock_valuation

router = APIRouter(prefix="/api/v1", tags=["financial-rag"])

# Live-only mode (2026-09-15): the snapshot/live_api manual switch was removed
# per user request — this system now always fetches real-time data via
# yfinance and there is no UI/API path to change that.
DATA_SOURCE_MODE = "live_api"


@router.get("/health")
async def health_check():
    retriever = get_shared_retriever()
    return {
        "status": "healthy",
        "service": "financial-rag-agent",
        "indexed_documents": len(retriever.documents),
        "mcp_server": "active",
        "data_source_mode": DATA_SOURCE_MODE,
        "timestamp": time.time(),
    }


@router.get("/settings")
async def get_settings():
    return {
        "data_source_mode": DATA_SOURCE_MODE,
        "label": "リアルタイム金融API (Live yfinance)",
        "badge": "⚡ LIVE API",
        "description": "東京証券取引所(.T)・為替(USD/JPY)・日経225のリアルタイム取得。手動切替は廃止済み。",
    }


@router.get("/documents/{doc_id}")
async def get_document_detail(doc_id: str):
    """Retrieve full text and metadata for a specific document or MCP citation source."""
    retriever = get_shared_retriever()

    # 1. Look up in indexed documents
    if doc_id in retriever.documents:
        doc = retriever.documents[doc_id]
        return {
            "status": "success",
            "type": "document",
            "id": doc.id,
            "title": doc.title,
            "ticker": doc.ticker,
            "company_name": doc.company_name,
            "source": doc.source,
            "date": doc.date,
            "category": doc.category,
            "content": doc.content,
            "metadata": doc.metadata,
        }

    # 2. Look up in MCP Valuation sources (e.g. mcp_val_6758, mcp_val_7203)
    if doc_id.startswith("mcp_val_"):
        ticker = doc_id.replace("mcp_val_", "").strip()
        from src.mcp_server.tools.valuation_tools import get_stock_valuation
        try:
            val_data = get_stock_valuation(ticker, mode=DATA_SOURCE_MODE)
            comp_name = val_data.get("company_name", f"Ticker {ticker}")
            content_summary = (
                f"{comp_name}（証券コード: {ticker}）の資本コスト・財務指標詳細データです。\n\n"
                f"■ 主な財務指標:\n"
                f"・予想PER (株価収益率): {val_data.get('per')}倍\n"
                f"・PBR (株価純資産倍率): {val_data.get('pbr')}倍 (東証1倍割れ改善指針)\n"
                f"・ROE (自己資本利益率): {val_data.get('roe_percent')}%\n"
                f"・TSR (株主総利回り): {val_data.get('tsr_percent')}%\n"
                f"・時価総額: {val_data.get('market_cap_trillion_jpy')}兆円\n"
                f"・配当利回り: {val_data.get('dividend_yield_percent')}%\n"
                f"・営業利益率: {val_data.get('operating_profit_margin_percent')}%\n\n"
                f"■ 企業価値評価ステータス: 『{val_data.get('valuation_status')}』\n"
                f"■ Value Trap (バリュートラップ) 判定: 『{val_data.get('value_trap_risk')}』"
            )
            return {
                "status": "success",
                "type": "mcp_valuation",
                "id": doc_id,
                "title": f"{comp_name}（{ticker}）財務・バリュエーション指標 (MCP)",
                "ticker": ticker,
                "company_name": comp_name,
                "source": "Model Context Protocol (MCP Server)",
                "date": val_data.get("as_of_date", "2025/2026"),
                "category": "財務モデル・開示指標",
                "content": content_summary,
                "metrics": val_data,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching MCP valuation for {ticker}: {str(e)}")

    # 3. Look up in MCP Disclosure sources (e.g. mcp_disc_7203, mcp_disc_6758)
    if doc_id.startswith("mcp_disc_"):
        ticker = doc_id.replace("mcp_disc_", "").strip()
        from src.mcp_server.tools.disclosure_tools import get_financial_disclosure
        try:
            disc_data = get_financial_disclosure(ticker, mode=DATA_SOURCE_MODE)
            comp_name = disc_data.get("company_name", f"Ticker {ticker}")
            catalysts_str = "、".join(disc_data.get("major_catalysts", []))
            content_summary = (
                f"{comp_name}（証券コード: {ticker}）の決算開示・業績ガイダンス詳細データです。\n\n"
                f"■ 決算期: {disc_data.get('fiscal_year')}\n"
                f"■ 売上高: {disc_data.get('revenue_billion_jpy')}億円\n"
                f"■ 営業利益: {disc_data.get('operating_income_billion_jpy')}億円\n"
                f"■ 当期純利益: {disc_data.get('net_income_billion_jpy')}億円\n\n"
                f"■ ガイダンス修正・重要開示:\n{disc_data.get('guidance_revision')}\n\n"
                f"■ 主要カタリスト・成長牽引材料:\n{catalysts_str}"
            )
            return {
                "status": "success",
                "type": "mcp_disclosure",
                "id": doc_id,
                "title": f"{comp_name}（{ticker}）決算開示・業績ガイダンス (MCP)",
                "ticker": ticker,
                "company_name": comp_name,
                "source": "東京証券取引所 TDnet / MCP 開示速報",
                "date": disc_data.get("fiscal_year", "最新開示"),
                "category": "適時開示・決算速報",
                "content": content_summary,
                "metrics": disc_data,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching MCP disclosure for {ticker}: {str(e)}")

    # 4. Macro indicator lookup
    if "macro" in doc_id or "boj" in doc_id:
        from src.mcp_server.tools.disclosure_tools import get_macro_indicators
        try:
            macro_list = get_macro_indicators(mode=DATA_SOURCE_MODE)
            macro_content = "日本銀行および為替・株式市場のマクロ経済指標スナップショットです。\n\n"
            for item in macro_list:
                macro_content += f"・{item.get('indicator')}: {item.get('value')} (トレンド: {item.get('trend')}, 提供: {item.get('source')})\n"
            return {
                "status": "success",
                "type": "mcp_macro",
                "id": doc_id,
                "title": "日本銀行金融政策およびマクロ経済指標 (MCP)",
                "ticker": "MACRO",
                "company_name": "日本銀行・為替市場",
                "source": "Model Context Protocol / 日銀・東証公表値",
                "date": macro_list[0].get("updated_at", "N/A") if macro_list else "N/A",
                "category": "マクロ経済・金融政策",
                "content": macro_content,
                "metrics": macro_list,
            }
        except Exception:
            pass

    # 5. Fallback substring search in retriever documents
    for k, doc in retriever.documents.items():
        if doc_id.lower() in k.lower() or k.lower() in doc_id.lower():
            return {
                "status": "success",
                "type": "document",
                "id": doc.id,
                "title": doc.title,
                "ticker": doc.ticker,
                "company_name": doc.company_name,
                "source": doc.source,
                "date": doc.date,
                "category": doc.category,
                "content": doc.content,
                "metadata": doc.metadata,
            }

    raise HTTPException(status_code=404, detail=f"Document or citation source '{doc_id}' not found.")


@router.get("/citations/{doc_id}")
async def get_citation_detail(doc_id: str):
    """Alias for /documents/{doc_id} to support citation links."""
    return await get_document_detail(doc_id)


# --- 自選銘柄 (Watchlist) -----------------------------------------------
# No auth/user model exists in this app (session_id is per-conversation, not
# per-account — see chat_sync below), so this is a single global list backed
# by data/watchlist.json. See src/services/watchlist.py for the full design
# rationale, including why "periodic rating" doesn't need a new scheduler.


@router.get("/watchlist")
async def list_watchlist_items():
    return {"items": watchlist_service.list_watchlist()}


@router.post("/watchlist")
async def add_watchlist_item(request: WatchlistAddRequest):
    resolved = watchlist_service.resolve_ticker_input(request.ticker)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"銘柄を特定できませんでした: '{request.ticker}'（証券コード4桁または正式な会社名でお試しください）",
        )

    valuation = await asyncio.to_thread(fetch_live_stock_valuation, resolved)
    if valuation.get("error"):
        raise HTTPException(status_code=404, detail=f"銘柄データを取得できませんでした: {resolved}")

    entry = watchlist_service.add_ticker(resolved, valuation.get("company_name", resolved))
    return {"status": "success", "item": entry}


@router.delete("/watchlist/{ticker}")
async def remove_watchlist_item(ticker: str):
    removed = watchlist_service.remove_ticker(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"ウォッチリストに '{ticker}' は登録されていません")
    return {"status": "success"}


@router.get("/watchlist/ratings")
async def get_watchlist_ratings():
    """Live, deterministic buy/hold/caution rating per watchlisted stock —
    the same rule table the chat report's layman verdict section uses (see
    src/services/watchlist.py docstring)."""
    items = await asyncio.to_thread(watchlist_service.get_watchlist_with_ratings)
    return {"items": items, "generated_at": time.time()}



@router.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Synchronous chat endpoint executing full LangGraph workflow."""
    start_time = time.time()
    session_id = request.session_id or f"session-{int(time.time())}"
    mode = DATA_SOURCE_MODE

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
    mode = DATA_SOURCE_MODE

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
                            "top_chunks": [
                                {
                                    "id": c.get("id"),
                                    "title": c.get("title", c.get("id")),
                                    "ticker": c.get("ticker"),
                                    "company_name": c.get("company_name"),
                                    "date": c.get("date"),
                                    "category": c.get("category"),
                                    "source": c.get("source", "日経電子版 / TDnet"),
                                    "rrf_score": round(float(c.get("rrf_score", 0.0)), 4),
                                    "content": (c.get("content", "")[:140] + "...") if len(c.get("content", "")) > 140 else c.get("content", ""),
                                }
                                for c in chunks[:5]
                            ],
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
                    synth_trace = next(
                        (t for t in node_state.get("execution_trace", []) if t.get("node") == "synthesizer"),
                        {},
                    )
                    llm_provider = synth_trace.get("llm_provider", "template")
                    yield {
                        "event": "synthesis_meta",
                        "data": json.dumps({
                            "llm_provider": llm_provider,
                            "is_real_llm": llm_provider != "template",
                            "duration_ms": synth_trace.get("duration_ms", 0),
                        }, ensure_ascii=False),
                    }
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
