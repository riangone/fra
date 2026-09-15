"""Production MCP Server implementation exposing Japanese market valuation and financial disclosures."""

import json
from typing import List, Dict, Any, Optional
from mcp.server.mcpserver import MCPServer
from src.mcp_server.tools.valuation_tools import get_stock_valuation, compare_companies
from src.mcp_server.tools.disclosure_tools import get_financial_disclosure, get_macro_indicators

# Initialize MCP Server
mcp_server = MCPServer(name="financial-tools-server", version="1.0.0")


@mcp_server.tool(
    name="get_stock_valuation",
    description="Fetch core valuation metrics (PER, PBR, ROE, TSR, Value Trap Risk) for Tokyo Stock Exchange tickers. Mode can be 'snapshot' or 'live_api'."
)
def tool_get_stock_valuation(ticker: str, mode: Optional[str] = None) -> str:
    res = get_stock_valuation(ticker, mode=mode)
    return json.dumps(res, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="compare_companies",
    description="Compare financial metrics across multiple tickers in the same industry or peer group. Mode can be 'snapshot' or 'live_api'."
)
def tool_compare_companies(tickers: List[str], mode: Optional[str] = None) -> str:
    res = compare_companies(tickers, mode=mode)
    return json.dumps(res, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="get_financial_disclosure",
    description="Fetch latest earnings report (revenue, operating income, net income, guidance revisions, major business catalysts) for a given ticker."
)
def tool_get_financial_disclosure(ticker: str, mode: Optional[str] = None) -> str:
    res = get_financial_disclosure(ticker, mode=mode)
    return json.dumps(res, ensure_ascii=False, indent=2)


@mcp_server.tool(
    name="get_macro_indicators",
    description="Fetch current macroeconomic indicators for Japan (BOJ Policy Interest Rate, Nikkei 225, USD/JPY Exchange Rate). Mode can be 'snapshot' or 'live_api'."
)
def tool_get_macro_indicators(mode: Optional[str] = None) -> str:
    res = get_macro_indicators(mode=mode)
    return json.dumps(res, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp_server.run_stdio_async())
