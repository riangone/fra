"""MCP Tool Execution Node for Financial Metrics."""

import time
from typing import Dict, Any
from src.models.state import AgentState
from src.mcp_server.client import get_mcp_client
from config.settings import settings


async def mcp_tool_runner_node(state: AgentState) -> Dict[str, Any]:
    """Invokes financial MCP tools based on detected tickers, intent, and data source mode."""
    start_time = time.time()
    mcp_client = get_mcp_client()

    tickers = state.get("target_tickers", [])
    intent = state.get("intent", "general")
    mode = state.get("data_source_mode") or settings.data_source_mode

    metrics_list = []

    for ticker in tickers:
        if ticker == "MACRO":
            macro_data = await mcp_client.get_macro(mode=mode)
            metrics_list.extend(macro_data)
        else:
            val_data = await mcp_client.get_valuation(ticker, mode=mode)
            if "error" not in val_data:
                metrics_list.append(val_data)

            # If earnings or general intent, also fetch disclosures
            if intent in ["earnings", "general"]:
                disc_data = await mcp_client.get_disclosure(ticker, mode=mode)
                if "error" not in disc_data:
                    metrics_list.append(disc_data)

    trace = state.get("execution_trace", [])
    trace.append({
        "node": "mcp_tool_runner",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "data_source_mode": mode,
        "tools_called": [f"valuation_{t}" for t in tickers],
        "metrics_retrieved_count": len(metrics_list),
    })

    return {
        "financial_metrics": metrics_list,
        "execution_trace": trace,
    }
