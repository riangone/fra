"""Tests for the 自選銘柄 (Watchlist) store and rating service
(src/services/watchlist.py).

Network calls (fetch_live_stock_valuation / resolve_ticker_by_name) are
mocked throughout — these tests verify the store's CRUD/persistence
behavior and the rating service's shape/degradation logic, not yfinance
itself (that's exercised live, not in CI).
"""

import json

import pytest

from src.services import watchlist as ws


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "watchlist.json"


def test_list_empty_when_file_missing(store_path):
    assert ws.list_watchlist(store_path) == []


def test_add_then_list_roundtrip(store_path):
    entry = ws.add_ticker("7203", "トヨタ自動車", store_path)
    assert entry["ticker"] == "7203"
    assert "added_at" in entry

    items = ws.list_watchlist(store_path)
    assert len(items) == 1
    assert items[0]["ticker"] == "7203"
    assert items[0]["company_name"] == "トヨタ自動車"


def test_add_is_idempotent(store_path):
    ws.add_ticker("7203", "トヨタ自動車", store_path)
    ws.add_ticker("7203", "トヨタ自動車", store_path)
    assert len(ws.list_watchlist(store_path)) == 1


def test_remove_returns_true_and_removes(store_path):
    ws.add_ticker("7203", "トヨタ自動車", store_path)
    assert ws.remove_ticker("7203", store_path) is True
    assert ws.list_watchlist(store_path) == []


def test_remove_missing_returns_false(store_path):
    assert ws.remove_ticker("9999", store_path) is False


def test_corrupt_file_treated_as_empty(store_path):
    store_path.write_text("{not valid json", encoding="utf-8")
    assert ws.list_watchlist(store_path) == []


def test_write_is_valid_json_on_disk(store_path):
    ws.add_ticker("7203", "トヨタ自動車", store_path)
    with store_path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data[0]["ticker"] == "7203"


def test_resolve_ticker_input_trusts_bare_four_digit_code(monkeypatch):
    # Must not hit resolve_ticker_by_name (i.e. no network) for a raw code.
    monkeypatch.setattr(ws, "resolve_ticker_by_name", lambda text: (_ for _ in ()).throw(AssertionError("should not be called")))
    assert ws.resolve_ticker_input("7203") == "7203"


def test_resolve_ticker_input_delegates_company_name(monkeypatch):
    monkeypatch.setattr(ws, "resolve_ticker_by_name", lambda text: "6758")
    assert ws.resolve_ticker_input("ソニーグループ") == "6758"


def test_resolve_ticker_input_empty_returns_none():
    assert ws.resolve_ticker_input("") is None
    assert ws.resolve_ticker_input("   ") is None


def test_ratings_success_path(store_path, monkeypatch):
    ws.add_ticker("7203", "トヨタ自動車", store_path)

    def fake_fetch(ticker):
        return {
            "ticker": ticker,
            "company_name": "トヨタ自動車",
            "per": 8.5,
            "pbr": 0.95,
            "roe_percent": 13.8,
            "tsr_percent": 20.0,
            "dividend_yield_percent": 3.0,
            "valuation_status": "UNDERVALUED",
            "as_of_date": "2026-09-18 00:00 JST (Live yfinance API)",
        }

    monkeypatch.setattr(ws, "fetch_live_stock_valuation", fake_fetch)
    ratings = ws.get_watchlist_with_ratings(store_path)

    assert len(ratings) == 1
    r = ratings[0]
    assert r["rating_available"] is True
    assert r["valuation_status"] == "UNDERVALUED"
    assert r["valuation_status_label"] == "割安（UNDERVALUED）"
    assert "買い" in r["verdict_label"]
    assert r["citation_id"] == "mcp_val_7203"
    assert "投資助言" in r["disclaimer"]


def test_ratings_degrades_gracefully_on_fetch_error(store_path, monkeypatch):
    ws.add_ticker("9999", "架空銘柄", store_path)

    monkeypatch.setattr(ws, "fetch_live_stock_valuation", lambda ticker: {"error": "boom"})
    ratings = ws.get_watchlist_with_ratings(store_path)

    assert len(ratings) == 1
    assert ratings[0]["rating_available"] is False
    assert ratings[0]["ticker"] == "9999"
    # Item must survive even though its live fetch failed — the whole panel
    # must not drop entries just because one ticker's rating is unavailable.
    assert ratings[0]["company_name"] == "架空銘柄"


def test_ratings_empty_watchlist(store_path):
    assert ws.get_watchlist_with_ratings(store_path) == []
