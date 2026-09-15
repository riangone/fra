"""MCP Client adapter for calling financial MCP tools from LangGraph nodes."""

import json
from typing import Dict, Any, List, Optional
from src.mcp_server.server import mcp_server


class MCPFinancialClient:
    """Async Client wrapper to interact with MCP tools."""

    def __init__(self, server=mcp_server):
        self.server = server

    async def get_valuation(self, ticker: str, mode: Optional[str] = None) -> Dict[str, Any]:
        args = {"ticker": ticker}
        if mode:
            args["mode"] = mode
        result = await self.server.call_tool("get_stock_valuation", args)
        content_text = result.content[0].text if result.content else "{}"
        return json.loads(content_text)

    async def get_disclosure(self, ticker: str, mode: Optional[str] = None) -> Dict[str, Any]:
        args = {"ticker": ticker}
        if mode:
            args["mode"] = mode
        result = await self.server.call_tool("get_financial_disclosure", args)
        content_text = result.content[0].text if result.content else "{}"
        return json.loads(content_text)

    async def get_macro(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        args = {}
        if mode:
            args["mode"] = mode
        result = await self.server.call_tool("get_macro_indicators", args)
        content_text = result.content[0].text if result.content else "[]"
        return json.loads(content_text)

    async def compare(self, tickers: List[str], mode: Optional[str] = None) -> List[Dict[str, Any]]:
        args = {"tickers": tickers}
        if mode:
            args["mode"] = mode
        result = await self.server.call_tool("compare_companies", args)
        content_text = result.content[0].text if result.content else "[]"
        return json.loads(content_text)


_client_instance: Optional[MCPFinancialClient] = None


def get_mcp_client() -> MCPFinancialClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = MCPFinancialClient()
    return _client_instance
