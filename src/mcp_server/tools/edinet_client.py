"""EDINET (金融庁 / Financial Services Agency) disclosure client.

Fetches real regulatory filings -- Annual Securities Reports (有価証券報告書,
docTypeCode "120") -- from EDINET's public API v2 and turns their key summary
figures into short Japanese-language articles that match the schema of
data/sample_articles.json (src/models/document.py::Document). This is the
Tier 1 corpus-expansion path: it does NOT require a Nikkei license -- EDINET
is a free government disclosure system.

Why this exists: the "検索チャンク (Hybrid RRF)" panel is only ever as good
as data/sample_articles.json, which ships with 8 hand-written sample rows
covering 6 companies. scripts/ingest_edinet.py uses this module to pull real
filings for arbitrary tickers and append them to data/edinet_articles.json,
which src/graph/nodes/hybrid_search.py::get_shared_retriever() merges in
alongside the original samples.

Auth: EDINET API v2 requires a free "Subscription-Key" -- self-service
instant signup at https://api.edinet-fsa.go.jp/, no approval wait, no cost.
Set it as EDINET_API_KEY (config/settings.py::Settings.edinet_api_key). This
module raises EdinetAuthError (not a silent None) when the key is missing or
rejected, so the failure mode is loud, not a quiet empty corpus.

API shape reference (EDINET API v2, stable since 2023):
  - GET /documents.json?date=YYYY-MM-DD&type=2&Subscription-Key=...
    -> a per-day index of every filing submitted that date. There is no
    per-company or date-range endpoint -- EDINET only offers a daily index,
    so discovering a specific company's filing history means scanning
    backwards day by day (see search_filings()). This is a genuine, widely
    known limitation of EDINET, not a corner this module is cutting.
  - GET /documents/{docID}?type=5&Subscription-Key=...
    -> a zip containing the filing's XBRL data pre-flattened to CSV
    (UTF-16LE, tab-separated), one row per XBRL fact:
    "要素ID\t項目名\tコンテキストID\t相対年度\t連結・個別\t期間・時点\tユニットID\t値"
    fetch_summary_facts() pulls the handful of headline P/L elements
    (NetSales / OperatingIncome / OrdinaryIncome / Profit, consolidated,
    current fiscal year) out of that CSV.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"

# docTypeCode "120" == 有価証券報告書 (Annual Securities Report) -- the
# richest, most figure-dense filing type and a good match for the tone of
# the existing hand-written sample articles.
ANNUAL_REPORT_DOC_TYPE = "120"

# Consolidated (連結), current-fiscal-year XBRL element IDs for the four
# headline P/L figures, using the standard jpcrp_cor "Summary of Business
# Results" taxonomy that every listed company's 有価証券報告書 populates.
_SUMMARY_ELEMENTS: Dict[str, str] = {
    "jpcrp_cor:NetSalesSummaryOfBusinessResults": "売上高",
    "jpcrp_cor:OperatingIncomeSummaryOfBusinessResults": "営業利益",
    "jpcrp_cor:OrdinaryIncomeSummaryOfBusinessResults": "経常利益",
    "jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults": "親会社株主に帰属する当期純利益",
}
_CURRENT_YEAR_CONTEXT_HINTS = ("CurrentYearDuration", "CurrentYearInstant")


class EdinetAuthError(RuntimeError):
    """Raised when EDINET rejects the request for lack of / an invalid key."""


class EdinetClient:
    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key if api_key is not None else settings.edinet_api_key
        self.session = session or requests.Session()

    def _get(self, path: str, params: Dict[str, Any]) -> requests.Response:
        if not self.api_key:
            raise EdinetAuthError(
                "EDINET_API_KEY is not set. Get a free key instantly at "
                "https://api.edinet-fsa.go.jp/ and export it as EDINET_API_KEY."
            )
        params = {**params, "Subscription-Key": self.api_key}
        resp = self.session.get(f"{EDINET_API_BASE}{path}", params=params, timeout=30)
        if resp.status_code == 401:
            raise EdinetAuthError(f"EDINET rejected the subscription key (401): {resp.text[:200]}")
        resp.raise_for_status()
        return resp

    def list_filings_for_date(self, day: date) -> List[Dict[str, Any]]:
        """Return every filing submitted on `day` (metadata only, type=2)."""
        resp = self._get("/documents.json", {"date": day.isoformat(), "type": "2"})
        payload = resp.json()
        return payload.get("results", []) or []

    def search_filings(
        self,
        sec_code_4digit: str,
        doc_type_code: str = ANNUAL_REPORT_DOC_TYPE,
        lookback_days: int = 450,
        max_hits: int = 1,
    ) -> List[Dict[str, Any]]:
        """Scan backwards from today, day by day, for filings by `sec_code_4digit`.

        EDINET has no "give me company X's filings" endpoint -- only a daily
        index -- so this is a linear scan. 450 days comfortably covers one
        annual cycle (securities reports are filed ~3 months after fiscal
        year end, so a company on a March fiscal year files in June).
        Stops early once `max_hits` matches are found.
        """
        hits: List[Dict[str, Any]] = []
        today = date.today()
        for offset in range(lookback_days):
            day = today - timedelta(days=offset)
            try:
                filings = self.list_filings_for_date(day)
            except EdinetAuthError:
                raise
            except requests.RequestException as exc:
                logger.warning("EDINET list_filings_for_date(%s) failed: %s", day, exc)
                continue
            for f in filings:
                sec_code = (f.get("secCode") or "").strip()
                # EDINET's secCode is the 5-digit JPX code (4-digit ticker + check
                # digit), e.g. "72030" for Toyota's "7203".
                if sec_code[:4] == sec_code_4digit and f.get("docTypeCode") == doc_type_code:
                    hits.append(f)
                    if len(hits) >= max_hits:
                        return hits
        return hits

    def fetch_summary_facts(self, doc_id: str) -> Dict[str, str]:
        """Download a filing's CSV export (type=5) and extract headline P/L facts.

        Returns a dict of {Japanese label: value string with unit}, e.g.
        {"売上高": "45,095,325", "営業利益": "5,352,934", ...}. Missing /
        unparsable elements are simply absent from the result -- callers
        should treat a sparse or empty dict as "not enough to write a
        sentence about" rather than an error.
        """
        resp = self._get(f"/documents/{doc_id}", {"type": "5"})
        facts: Dict[str, str] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_names = [n for n in zf.namelist() if n.upper().endswith(".CSV")]
                for name in csv_names:
                    with zf.open(name) as fh:
                        raw = fh.read()
                    text = _decode_edinet_csv(raw)
                    facts.update(_extract_summary_facts(text))
        except zipfile.BadZipFile:
            logger.warning("EDINET doc %s: type=5 response was not a valid zip", doc_id)
        return facts


def _decode_edinet_csv(raw: bytes) -> str:
    """EDINET's CSV export is UTF-16LE with a BOM; fall back gracefully."""
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_summary_facts(csv_text: str) -> Dict[str, str]:
    """Parse EDINET's flattened XBRL-to-CSV rows for the headline elements
    defined in _SUMMARY_ELEMENTS, preferring consolidated (連結) /
    current-year rows when an element has multiple contexts.
    """
    facts: Dict[str, str] = {}
    reader = csv.reader(io.StringIO(csv_text), delimiter="\t")
    header: Optional[List[str]] = None
    for row in reader:
        if header is None:
            header = row
            continue
        if len(row) < 8:
            continue
        element_id, _item_name, context_id, _rel_year, consolidated, _period, _unit, value = row[:8]
        label = _SUMMARY_ELEMENTS.get(element_id)
        if not label or not value:
            continue
        is_current_year_context = any(hint in context_id for hint in _CURRENT_YEAR_CONTEXT_HINTS)
        is_consolidated = "連結" in consolidated or "Consolidated" in context_id
        if not is_current_year_context:
            continue
        # Prefer consolidated figures; only take a non-consolidated row if we
        # don't already have one for this label.
        if label in facts and not is_consolidated:
            continue
        facts[label] = value.strip()
    return facts


@dataclass
class EdinetFilingSummary:
    doc_id: str
    filer_name: str
    sec_code_4digit: str
    doc_description: str
    submit_date: str
    period_end: str
    facts: Dict[str, str]


def build_article_content(summary: EdinetFilingSummary) -> str:
    """Compose a short factual Japanese paragraph from extracted XBRL facts,
    in the same register as data/sample_articles.json's hand-written rows,
    but sourced entirely from figures actually present in the filing --
    nothing here is invented; if a fact is missing it is simply omitted.
    """
    parts = [
        f"{summary.filer_name}は{summary.submit_date}、EDINET上に{summary.doc_description}"
        f"（対象期間終了日: {summary.period_end}）を提出した。"
    ]
    fact_sentences = []
    for label in ("売上高", "営業利益", "経常利益", "親会社株主に帰属する当期純利益"):
        if label in summary.facts:
            fact_sentences.append(f"{label}は{summary.facts[label]}円")
    if fact_sentences:
        parts.append("連結業績（当期実績）は、" + "、".join(fact_sentences) + "。")
    parts.append("（出所: EDINET / 金融庁 有価証券報告書、機械抽出データにつき正確な数値は原文をご確認ください）")
    return "".join(parts)
