"""Tokyo Stock Exchange listed-company master (name <-> code), bundled locally.

Backed by data/tse_listed_companies.csv (3,712 rows: every TSE Prime/Standard/
Growth-listed domestic and foreign stock), generated from JPX's official
"東証上場銘柄一覧" (data_j.xlsx, published at
https://www.jpx.co.jp/markets/statistics-equities/misc/01.html). Regenerate
with `python scripts/refresh_tse_master.py` when JPX updates the list.

Why this exists: `live_market_client.resolve_ticker_by_name()`'s network
fallback uses yfinance's `Search` API, which does NOT index Japanese kanji
text at all -- confirmed by hand that a valid query like "武田薬品" returns
zero results, while the romanized "Takeda" resolves fine. Without a local
master, any kanji company name outside the small hardcoded
COMPANY_TICKER_MAP shortcut (query_rewriter.py) was permanently unresolvable.

This module is pure local CSV + in-memory list, no network calls, so it is
tried BEFORE the yfinance network fallback.
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "tse_listed_companies.csv"

# A prefix match shorter than this is too likely to collide with an unrelated
# company or a common surname fragment (e.g. a bare 2-char hit) -- refuse to
# guess rather than risk resolving to the wrong ticker.
_MIN_PREFIX_MATCH_LEN = 3
# Exact containment of the *whole* official name doesn't carry the same
# collision risk, so it's accepted down to a shorter floor.
_MIN_FULL_MATCH_LEN = 2

_MASTER: Optional[List[Tuple[str, str]]] = None  # (code, name), loaded once


def _load_master() -> List[Tuple[str, str]]:
    global _MASTER
    if _MASTER is not None:
        return _MASTER
    rows: List[Tuple[str, str]] = []
    try:
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                code = (row.get("code") or "").strip()
                name = (row.get("name") or "").strip()
                if code and name:
                    rows.append((code, name))
    except FileNotFoundError:
        logger.warning(
            "TSE master CSV not found at %s; kanji company-name resolution disabled "
            "(falls back to yfinance's romanized-only search).",
            CSV_PATH,
        )
    _MASTER = rows
    return _MASTER


def lookup_name_by_code(code: str) -> Optional[str]:
    """Return the official JPX-listed name for a 4-digit ticker code, or None."""
    clean = code.strip().upper()
    for c, name in _load_master():
        if c == clean:
            return name
    return None


def resolve_ticker_by_jp_name(text: str) -> Optional[str]:
    """Resolve a Japanese company name (full official name or a common
    abbreviated prefix) to its TSE ticker code via the bundled JPX master.

    Matching rules, cheapest-first conceptually but scored uniformly by
    match length so the most specific hit always wins:
      - Exact containment: the company's full official name appears verbatim
        in the input text.
      - Prefix containment: a prefix of the company's full name (>=3 chars)
        appears in the input text -- covers the common case where users drop
        a generic trailing word like 工業/製作所/ホールディングス (e.g. users
        typing "武田薬品" for the officially listed "武田薬品工業").

    Returns None (never raises) if nothing matches, or if two or more
    *different* companies tie for the best (longest) match -- ambiguous
    cases are not guessed at.
    """
    query = text.strip()
    if not query:
        return None

    best_len = 0
    best_code: Optional[str] = None
    ambiguous = False

    for code, name in _load_master():
        match_len = 0
        if name in query:
            match_len = len(name)
        else:
            for length in range(len(name), _MIN_PREFIX_MATCH_LEN - 1, -1):
                if name[:length] in query:
                    match_len = length
                    break

        if match_len == 0 or match_len < _MIN_FULL_MATCH_LEN:
            continue

        if match_len > best_len:
            best_len = match_len
            best_code = code
            ambiguous = False
        elif match_len == best_len and code != best_code:
            ambiguous = True

    if ambiguous:
        logger.info(
            "Ambiguous kanji company-name match for %r (multiple TSE-listed "
            "companies tie on match length); refusing to guess.",
            text,
        )
        return None
    return best_code
