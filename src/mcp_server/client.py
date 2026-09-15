"""MCP Client adapter for calling financial MCP tools from LangGraph nodes."""

import json
from typing import Dict, Any, List, Optional
from src.mcp_server.server import mcp_server


class MCPFinancialClient:
    """Async Client wrapper to interact with MCP tools."""

    def __init__(self, server=mcp_server):
        self.server = server

    async def get_valuation(self, ticker: str) -> Dict[str, Any]:
        result = await self.server.call_tool("get_stock_valuation", {"ticker": ticker})
        content_text = result.content[0].text if result.content else "{}"
        return json.loads(content_text)

    async def get_disclosure(self, ticker: str) -> Dict[str, Any]:
        result = await self.server.call_tool("get_financial_disclosure", {"ticker": ticker})
        content_text = result.content[0].text if result.content else "{}"
        return json.loads(content_text)

    async def get_macro(self) -> List[Dict[str, Any]]:
        result = await self.server.call_tool("get_macro_indicators", {})
        content_text = result.content[0].text if result.content else "[]"
        return json.loads(content_text)

    async def compare(self, tickers: List[str]) -> List[Dict[str, Any]]:
        result = await self.server.call_tool("compare_companies", {"tickers": tickers})
        content_text = result.content[0].text if result.content else "[]"
        return json.loads(content_text)


_client_instance: Optional[MCPFinancialClient] = None


def get_mcp_client() -> MCPFinancialClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPFinancialClient()
    return _client_instance
