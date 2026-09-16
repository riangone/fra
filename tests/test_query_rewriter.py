"""Unit tests for the Query Rewriter node's ticker-detection layers.

Mirrors the project's existing convention (see test_mcp_tools.py) of hitting
the real yfinance-backed resolution path rather than mocking it, since these
tests exist specifically to prove ticker detection is no longer limited to
the hardcoded COMPANY_TICKER_MAP whitelist.
"""

import pytest
from src.graph.nodes.query_rewriter import query_rewriter_node


@pytest.mark.asyncio
async def test_curated_alias_still_resolves_without_network():
    """Companies in the curated map keep working via the zero-network fast path."""
    state = {"query": "トヨタのPERを教えて", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["7203"]
    trace = result["execution_trace"][-1]
    assert trace["resolved_via_free_text_search"] is False


@pytest.mark.asyncio
async def test_raw_ticker_code_resolves_without_registration():
    """A bare 4-digit ticker code works even though it's not in the curated map."""
    state = {"query": "4502の株価を教えて", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["4502"]


@pytest.mark.asyncio
async def test_fiscal_year_mention_is_not_mistaken_for_a_ticker():
    """'2024年3月期' must not be parsed as ticker code 2024."""
    state = {"query": "トヨタの2024年3月期決算はどうでしたか", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["7203"]
    assert "2024" not in result["target_tickers"]


@pytest.mark.asyncio
async def test_free_form_english_company_name_resolves_dynamically():
    """A company absent from COMPANY_TICKER_MAP still resolves via live search."""
    state = {"query": "Takedaの株価は？", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["4502"]
    trace = result["execution_trace"][-1]
    assert trace["resolved_via_free_text_search"] is True


@pytest.mark.asyncio
async def test_free_form_kanji_company_name_resolves_via_local_master():
    """Kanji company names outside COMPANY_TICKER_MAP now resolve via the
    bundled TSE master (data/tse_listed_companies.csv) — this is the fix for
    the previously known limitation where Yahoo Finance's search API could
    not resolve any kanji query (it only indexes romanized/English text)."""
    state = {"query": "武田薬品の株価を教えて", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["4502"]
    trace = result["execution_trace"][-1]
    assert trace["resolved_via_free_text_search"] is True


@pytest.mark.asyncio
async def test_unresolvable_query_degrades_to_empty_tickers_not_an_error():
    """Free-text lookup failures/misses must never raise; they just yield []."""
    state = {"query": "こんにちは、今日の天気は？", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == []


@pytest.mark.asyncio
async def test_macro_query_skips_free_text_network_lookup():
    """Pure macro questions resolve via MACRO alias and never touch the network."""
    state = {"query": "日銀の金融政策について教えて", "execution_trace": []}
    result = await query_rewriter_node(state)
    assert result["target_tickers"] == ["MACRO"]
    trace = result["execution_trace"][-1]
    assert trace["resolved_via_free_text_search"] is False
