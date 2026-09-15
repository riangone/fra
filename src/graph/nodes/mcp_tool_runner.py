"""MCP Tool Execution Node for Financial Metrics."""

import time
from typing import Dict, Any
from src.models.state import AgentState
from src.mcp_server.client import get_mcp_client


async def mcp_tool_runner_node(state: AgentState) -> Dict[str, Any]:
    """Invokes financial MCP tools based on detected tickers and intent."""
    start_time = time.time()
    mcp_client = get_mcp_client()

    tickers = state.get("target_tickers", [])
    intent = state.get("intent", "general")

    metrics_list = []

    for ticker in tickers:
        if ticker == "MACRO":
            macro_data = await mcp_client.get_macro()
            metrics_list.extend(macro_data)
        else:
            val_data = await mcp_client.get_valuation(ticker)
            if "error" not in val_data:
                metrics_list.append(val_data)

            # If earnings or general intent, also fetch disclosures
            if intent in ["earnings", "general"]:
                disc_data = await mcp_client.get_disclosure(ticker)
                if "error" not in disc_data:
                    metrics_list.append(disc_data)

    trace = state.get("execution_trace", [])
    trace.append({
        "node": "mcp_tool_runner",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "tools_called": [f"valuation_{t}" for t in tickers],
        "metrics_retrieved_count": len(metrics_list),
    })

    return {
        "financial_metrics": metrics_list,
        "execution_trace": trace,
    }
