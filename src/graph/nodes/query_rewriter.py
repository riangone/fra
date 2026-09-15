"""Query Rewriting and Intent Classification Node."""

import re
import time
from typing import Dict, Any, List
from src.models.state import AgentState

# Known ticker mappings for Japanese markets
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
    "日銀": "MACRO",
    "日本銀行": "MACRO",
    "為替": "MACRO",
    "ドル円": "MACRO",
    "金利": "MACRO",
}


def query_rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts tickers, identifies financial query intent, and rewrites the query
    for optimal hybrid retrieval.
    """
    start_time = time.time()
    query = state.get("query", "").strip()
    query_lower = query.lower()

    # Detect tickers
    detected_tickers = []
    for name, ticker in COMPANY_TICKER_MAP.items():
        if name in query_lower:
            if ticker not in detected_tickers:
                detected_tickers.append(ticker)

    # Detect intent
    intent = "general"
    if any(k in query_lower for k in ["per", "pbr", "roe", "tsr", "割安", "割高", "バリュエーション", "配当"]):
        intent = "valuation"
    elif any(k in query_lower for k in ["決算", "売上", "営業利益", "純利益", "上方修正", "下方修正", "業績"]):
        intent = "earnings"
    elif any(k in query_lower for k in ["利上げ", "金利", "日銀", "為替", "円高", "円安", "日経平均"]):
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
    })

    return {
        "rewritten_query": rewritten_query,
        "target_tickers": detected_tickers,
        "intent": intent,
        "execution_trace": trace,
    }
