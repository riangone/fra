"""Unit tests for MCP Financial Tools and Client."""

import pytest
from src.mcp_server.tools.valuation_tools import get_stock_valuation, compare_companies
from src.mcp_server.tools.disclosure_tools import get_financial_disclosure, get_macro_indicators
from src.mcp_server.client import get_mcp_client


def test_valuation_tool():
    val = get_stock_valuation("7203")
    assert "error" not in val
    assert val["ticker"] == "7203"
    assert val["per"] == 9.2
    assert val["pbr"] == 1.05
    assert val["valuation_status"] == "UNDERVALUED"


def test_compare_tool():
    comp = compare_companies(["7203", "6758"])
    assert len(comp) == 2
    assert comp[0]["ticker"] == "7203"
    assert comp[1]["ticker"] == "6758"


def test_disclosure_and_macro_tools():
    disc = get_financial_disclosure("7203")
    assert "error" not in disc
    assert disc["revenue_billion_jpy"] > 40000

    macro = get_macro_indicators()
    assert len(macro) >= 3
    assert any("0.25%" in m["value"] for m in macro)


@pytest.mark.asyncio
async def test_mcp_client_async():
    client = get_mcp_client()
    val = await client.get_valuation("6758")
    assert val["ticker"] == "6758"
    assert val["company_name"] == "ソニーグループ"
