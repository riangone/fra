"""自選銘柄 (Watchlist) store + periodic-rating service.

Design notes (Architect-level decisions worth spelling out):

1. Persistence: a flat JSON file (`data/watchlist.json`), matching this
   project's existing convention for small corpora (`data/sample_articles.json`,
   `data/edinet_articles.json`) rather than introducing a database dependency
   for a single-tenant demo app. There is no auth/user model anywhere in this
   codebase (see `src/api/routes.py` — `session_id` is per-conversation, not
   per-account), so the watchlist is intentionally a single global list, not
   scoped per user.

2. "Periodic rating" without a scheduler: rather than adding a cron/APScheduler
   dependency to recompute ratings server-side on a timer, this reuses the
   TTL cache already inside `fetch_live_stock_valuation()`
   (`live_market_client._CACHE`, 5 minutes). `get_watchlist_with_ratings()` is
   cheap to call on every page load/refresh — first call per ticker per 5-min
   window hits yfinance, everything else is served from that cache. The
   frontend polls this endpoint on an interval, which is functionally a
   periodic rating without any new background-job infrastructure.

3. The buy/hold/caution label and the bilingual status string are NOT
   recomputed here — they are imported from `live_market_client`, the same
   functions the chat report's layman verdict section uses
   (`src/graph/nodes/synthesizer.py`), so a stock always gets the same call
   whether it's rendered inside a synthesized report or in the watchlist
   panel.
"""

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.mcp_server.tools.live_market_client import (
    bilingual_valuation_status,
    fetch_live_stock_valuation,
    layman_verdict_label,
    resolve_ticker_by_name,
)

logger = logging.getLogger("financial_rag.watchlist")

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "watchlist.json"
_LOCK = threading.Lock()
_TICKER_CODE_RE = re.compile(r"^\d{4}$")


def _read(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("watchlist file unreadable (%s); treating as empty", e)
        return []


def _write(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)  # atomic on POSIX — avoids a torn file if the
    # process is killed mid-write (same reload-safety concern as the
    # double-process incident: a partial JSON file must never be readable).


def resolve_ticker_input(raw: str) -> Optional[str]:
    """Resolve free-form watchlist-add input to a 4-digit TSE ticker code.

    Mirrors the layered resolution already used by query_rewriter_node
    (src/graph/nodes/query_rewriter.py): a bare 4-digit code is trusted
    directly (no network call); anything else goes through
    resolve_ticker_by_name (local JPX master first, yfinance search second).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if _TICKER_CODE_RE.match(raw):
        return raw
    return resolve_ticker_by_name(raw)


def list_watchlist(path: Path = DATA_PATH) -> List[Dict[str, Any]]:
    with _LOCK:
        return _read(path)


def add_ticker(ticker: str, company_name: str, path: Path = DATA_PATH) -> Dict[str, Any]:
    with _LOCK:
        items = _read(path)
        existing = next((i for i in items if i["ticker"] == ticker), None)
        if existing:
            return existing
        entry = {
            "ticker": ticker,
            "company_name": company_name,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        items.append(entry)
        _write(path, items)
        return entry


def remove_ticker(ticker: str, path: Path = DATA_PATH) -> bool:
    with _LOCK:
        items = _read(path)
        remaining = [i for i in items if i["ticker"] != ticker]
        if len(remaining) == len(items):
            return False
        _write(path, remaining)
        return True


def get_watchlist_with_ratings(path: Path = DATA_PATH) -> List[Dict[str, Any]]:
    """Attach a live, deterministic rating to every stored ticker.

    A per-ticker fetch failure (network hiccup, delisted code, etc.) never
    drops the item from the list or crashes the whole panel — it degrades to
    `rating_available: False` with the last-known name so the user still
    sees the ticker they added and can retry later.
    """
    results: List[Dict[str, Any]] = []
    for item in list_watchlist(path):
        ticker = item["ticker"]
        valuation = fetch_live_stock_valuation(ticker)
        if valuation.get("error"):
            results.append(
                {
                    "ticker": ticker,
                    "company_name": item.get("company_name", ticker),
                    "added_at": item.get("added_at"),
                    "rating_available": False,
                    "error": valuation["error"],
                }
            )
            continue

        status = valuation.get("valuation_status", "FAIR")
        roe = valuation.get("roe_percent", 0.0) or 0.0
        results.append(
            {
                "ticker": ticker,
                "company_name": valuation.get("company_name", item.get("company_name", ticker)),
                "added_at": item.get("added_at"),
                "rating_available": True,
                "valuation_status": status,
                "valuation_status_label": bilingual_valuation_status(status),
                "per": valuation.get("per"),
                "pbr": valuation.get("pbr"),
                "roe_percent": roe,
                "tsr_percent": valuation.get("tsr_percent"),
                "dividend_yield_percent": valuation.get("dividend_yield_percent"),
                "verdict_label": layman_verdict_label(status, roe),
                "as_of_date": valuation.get("as_of_date"),
                "citation_id": f"mcp_val_{ticker}",
                "disclaimer": "投資助言・売買推奨ではありません。最終判断はご自身の責任で。",
            }
        )
    return results
