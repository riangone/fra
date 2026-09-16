"""Query Rewriting and Intent Classification Node."""

import re
import time
import asyncio
from typing import Dict, Any, List
from src.models.state import AgentState
from src.mcp_server.tools.live_market_client import resolve_ticker_by_name

# Curated fast-path aliases: common JP company names/abbreviations that map
# straight to a ticker with zero network cost. This is now a SHORTCUT, not a
# whitelist — companies outside this dict are still resolvable (see below).
COMPANY_TICKER_MAP = {
    "トヨタ": "7203",
    "toyota": "7203",
    "7203": "7203",
    "ソニー": "6758",
    "sony": "6758",
    "6758": "6758",
    "ソフトバンク": "9984",
    "softbank": "9984",
    "sbg": "9984",
    "9984": "9984",
    "三菱ufj": "8306",
    "mufg": "8306",
    "8306": "8306",
    "東京エレクトロン": "8035",
    "tel": "8035",
    "8035": "8035",
    "ihi": "7013",
    "7013": "7013",
    "日銀": "MACRO",
    "日本銀行": "MACRO",
    "為替": "MACRO",
    "ドル円": "MACRO",
    "金利": "MACRO",
}

MACRO_KEYWORDS = ["利上げ", "金利", "日銀", "為替", "円高", "円安", "日経平均"]

# A bare 4-digit number in the query is very likely a TSE ticker code typed
# directly by the user (e.g. "4502の株価は?") — resolve it without any
# network round-trip, regardless of whether it's in the curated map above.
# Excludes numbers immediately followed by "年" so fiscal-year mentions like
# "2024年3月期" aren't misread as a ticker code.
_TICKER_CODE_PATTERN = re.compile(r"(?<!\d)\d{4}(?!\d)(?!年)")


async def query_rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts tickers, identifies financial query intent, and rewrites the query
    for optimal hybrid retrieval.

    Ticker detection is layered, cheapest-first:
      1. Curated alias map (instant, covers common JP names/macro terms).
      2. Raw 4-digit ticker codes typed directly in the query (instant).
      3. Free-form company name resolution (resolve_ticker_by_name), only
         attempted when 1+2 found nothing and the query doesn't look like a
         pure macro question. Internally two-layered itself:
           3a. Local TSE-listed company master lookup (data/tse_listed_companies.csv,
               instant, no network) — resolves any of the ~3,700 JPX-listed
               companies by kanji name, not just the ones hardcoded in
               COMPANY_TICKER_MAP. This is the layer that makes kanji names
               work at all, since Yahoo's search API (3b) doesn't index kanji.
           3b. yfinance free-form search (network) — covers English/romanized
               names not in the local master.
    """
    start_time = time.time()
    query = state.get("query", "").strip()
    query_lower = query.lower()

    # 1. Curated alias map
    detected_tickers: List[str] = []
    for name, ticker in COMPANY_TICKER_MAP.items():
        if name in query_lower:
            if ticker not in detected_tickers:
                detected_tickers.append(ticker)

    # 2. Raw 4-digit ticker codes
    for code in _TICKER_CODE_PATTERN.findall(query):
        if code not in detected_tickers:
            detected_tickers.append(code)

    # 3. Free-form resolution fallback (network), skipped on the hot path
    resolved_free_form = False
    if not detected_tickers and not any(k in query_lower for k in MACRO_KEYWORDS):
        resolved = await asyncio.to_thread(resolve_ticker_by_name, query)
        if resolved:
            detected_tickers.append(resolved)
            resolved_free_form = True

    # Detect intent
    intent = "general"
    if any(k in query_lower for k in ["per", "pbr", "roe", "tsr", "割安", "割高", "バリュエーション", "配当"]):
        intent = "valuation"
    elif any(k in query_lower for k in ["決算", "売上", "営業利益", "純利益", "上方修正", "下方修正", "業績"]):
        intent = "earnings"
    elif any(k in query_lower for k in MACRO_KEYWORDS):
        intent = "macro"
    elif len(detected_tickers) > 1 or any(k in query_lower for k in ["比較", "対比", "競合"]):
        intent = "comparison"

    # Query Rewriting
    rewritten_tokens = [query]
    if detected_tickers:
        for t in detected_tickers:
            if t != "MACRO":
                rewritten_tokens.append(f"銘柄コード {t}")
    if intent == "valuation":
        rewritten_tokens.append("株価純資産倍率 資本コスト 経営効率")
    elif intent == "earnings":
        rewritten_tokens.append("通期連結決算 業績予想 営業増益")
    elif intent == "macro":
        rewritten_tokens.append("金融政策決定会合 政策金利")

    rewritten_query = " ".join(rewritten_tokens)

    trace = state.get("execution_trace", [])
    trace.append({
        "node": "query_rewriter",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "detected_tickers": detected_tickers,
        "intent": intent,
        "rewritten_query": rewritten_query,
        "resolved_via_free_text_search": resolved_free_form,
    })

    return {
        "rewritten_query": rewritten_query,
        "target_tickers": detected_tickers,
        "intent": intent,
        "execution_trace": trace,
    }
