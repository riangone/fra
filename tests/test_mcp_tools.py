"""Unit tests for MCP Financial Tools and Client."""

import pytest
from src.mcp_server.tools.valuation_tools import get_stock_valuation, compare_companies
from src.mcp_server.tools.disclosure_tools import get_financial_disclosure, get_macro_indicators
from src.mcp_server.tools.live_market_client import resolve_ticker_by_name
from src.mcp_server.client import get_mcp_client


def test_valuation_tool():
    val = get_stock_valuation("7203")
    assert "error" not in val
    assert val["ticker"] == "7203"
    # Range checks accommodate Live market price / valuation fluctuation
    assert 5.0 < val["per"] < 15.0
    assert 0.5 < val["pbr"] < 2.0
    assert val["valuation_status"] in ["UNDERVALUED", "FAIR", "OVERVALUED"]


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


def test_resolve_ticker_by_name_free_form():
    """Companies outside the curated JP_TICKER_NAMES/COMPANY_TICKER_MAP maps
    must still resolve to a TSE ticker via live search, and the result must
    be cached for repeat lookups."""
    resolved = resolve_ticker_by_name("Takeda")
    assert resolved == "4502"
    # Second call should hit the in-memory cache and return the same value.
    assert resolve_ticker_by_name("Takeda") == "4502"


def test_resolve_ticker_by_name_returns_none_for_garbage():
    """Nonsense input must degrade to None, never raise."""
    assert resolve_ticker_by_name("") is None
    assert resolve_ticker_by_name("asdkjhqwe98237alksdjqwe") is None


def test_resolve_ticker_by_name_kanji_resolves_via_local_master_no_network():
    """A kanji company name outside COMPANY_TICKER_MAP must resolve via the
    bundled TSE master (data/tse_listed_companies.csv), since yfinance's
    search API does not index kanji text at all. This closes the previously
    documented gap where only curated/romanized names were resolvable."""
    assert resolve_ticker_by_name("武田薬品") == "4502"
    assert resolve_ticker_by_name("村田製作所") == "6981"


def test_stock_valuation_uses_tse_master_name_outside_curated_map():
    """A ticker outside the small curated JP_TICKER_NAMES map must still show
    its real Japanese company name (from the TSE master), not a bare code."""
    val = get_stock_valuation("4502")
    assert val["company_name"] == "武田薬品工業"


@pytest.mark.asyncio
async def test_mcp_client_async():
    client = get_mcp_client()
    val = await client.get_valuation("6758")
    assert val["ticker"] == "6758"
    assert val["company_name"] == "ソニーグループ"
