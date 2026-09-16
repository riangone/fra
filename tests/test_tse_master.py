"""Unit tests for the bundled TSE listed-company master (data/tse_listed_companies.csv)
and its resolver in src/mcp_server/tools/tse_master.py.

These are pure local/offline tests (no network) — the whole point of this
module is that kanji company-name resolution no longer depends on any
external API.
"""

from src.mcp_server.tools.tse_master import lookup_name_by_code, resolve_ticker_by_jp_name


def test_exact_official_name_resolves():
    assert resolve_ticker_by_jp_name("武田薬品工業") == "4502"


def test_abbreviated_prefix_resolves():
    """Users commonly drop a generic trailing word (here 工業) when referring
    to a company; the resolver should still find it via prefix matching."""
    assert resolve_ticker_by_jp_name("武田薬品の株価を教えて") == "4502"
    assert resolve_ticker_by_jp_name("村田製作所の業績は？") == "6981"


def test_match_works_regardless_of_surrounding_text():
    assert resolve_ticker_by_jp_name("キーエンスのPERとPBRを比較して") == "6861"
    assert resolve_ticker_by_jp_name("教えて、日立製作所は割安か") == "6501"


def test_fiscal_year_text_does_not_false_match():
    assert resolve_ticker_by_jp_name("2024年3月期の業績について") is None


def test_unknown_company_returns_none():
    assert resolve_ticker_by_jp_name("存在しない架空企業XYZ") is None


def test_empty_input_returns_none():
    assert resolve_ticker_by_jp_name("") is None
    assert resolve_ticker_by_jp_name("   ") is None


def test_ambiguous_short_fragment_refuses_to_guess():
    """A short group-name fragment shared by many unrelated companies (e.g.
    the many "三菱..." / "三井..." group companies) must not be guessed at —
    better to resolve nothing than to pick the wrong one of many candidates."""
    assert resolve_ticker_by_jp_name("三菱") is None
    assert resolve_ticker_by_jp_name("三井") is None


def test_lookup_name_by_code_returns_official_jpx_name():
    assert lookup_name_by_code("4502") == "武田薬品工業"
    assert lookup_name_by_code("6758") == "ソニーグループ"
    assert lookup_name_by_code("7203") == "トヨタ自動車"


def test_lookup_name_by_code_unknown_code_returns_none():
    assert lookup_name_by_code("0000") is None
