#!/usr/bin/env python3
"""Ingest real EDINET (金融庁) filings into the Hybrid RRF search corpus.

This is the Tier 1 corpus-expansion path discussed for the "検索チャンク
(Hybrid RRF)" panel, which otherwise only ever sees the 8 hand-written rows
in data/sample_articles.json. It does NOT require a Nikkei license: EDINET
is the FSA's free public disclosure system.

For each requested ticker, this script:
  1. Scans EDINET's daily filing index backwards to find that company's most
     recent Annual Securities Report (有価証券報告書, docTypeCode "120").
  2. Downloads the filing's XBRL-as-CSV export and extracts headline P/L
     figures (売上高 / 営業利益 / 経常利益 / 当期純利益).
  3. Composes a short factual Japanese article from those figures (nothing
     invented -- a missing figure is simply omitted).
  4. Appends/updates the result in data/edinet_articles.json, keyed by
     EDINET docID so re-running is idempotent (existing entries are left
     alone unless overwritten by a newer filing for the same company).

data/edinet_articles.json is loaded IN ADDITION to data/sample_articles.json
by src/graph/nodes/hybrid_search.py::get_shared_retriever() -- this script
never touches sample_articles.json itself.

Requires a free EDINET API key (instant self-service signup, no approval
wait): https://api.edinet-fsa.go.jp/ -> export EDINET_API_KEY=...

Usage:
    export EDINET_API_KEY=xxxxxxxx
    python scripts/ingest_edinet.py --tickers 7203,6758,9984,8306,8035,7013
    python scripts/ingest_edinet.py --tickers 7203 --lookback-days 450
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.tools.edinet_client import (  # noqa: E402
    EdinetClient,
    EdinetAuthError,
    EdinetFilingSummary,
    build_article_content,
)
from src.mcp_server.tools.tse_master import lookup_name_by_code  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ingest_edinet")

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "edinet_articles.json"


def ingest_ticker(client: EdinetClient, ticker: str, lookback_days: int) -> dict | None:
    logger.info("Searching EDINET for ticker %s (lookback=%d days)...", ticker, lookback_days)
    hits = client.search_filings(ticker, lookback_days=lookback_days, max_hits=1)
    if not hits:
        logger.warning("No 有価証券報告書 found for %s within %d days.", ticker, lookback_days)
        return None

    filing = hits[0]
    doc_id = filing["docID"]
    filer_name = filing.get("filerName") or lookup_name_by_code(ticker) or f"銘柄コード{ticker}"
    logger.info("Found %s (docID=%s, submitted %s). Downloading facts...", filer_name, doc_id, filing.get("submitDateTime"))

    facts = client.fetch_summary_facts(doc_id)
    if not facts:
        logger.warning("docID=%s: no headline P/L facts could be extracted; skipping.", doc_id)
        return None

    summary = EdinetFilingSummary(
        doc_id=doc_id,
        filer_name=filer_name,
        sec_code_4digit=ticker,
        doc_description=filing.get("docDescription", "有価証券報告書"),
        submit_date=(filing.get("submitDateTime") or "")[:10],
        period_end=filing.get("periodEnd", ""),
        facts=facts,
    )
    content = build_article_content(summary)

    return {
        "id": f"doc_edinet_{ticker}_{doc_id}",
        "title": f"{filer_name} {summary.doc_description}（EDINET提出書類）",
        "ticker": ticker,
        "company_name": filer_name,
        "source": "EDINET（金融庁）",
        "date": summary.submit_date,
        "category": "有価証券報告書",
        "content": content,
        "metadata": {"edinet_doc_id": doc_id},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickers", required=True, help="Comma-separated 4-digit TSE ticker codes, e.g. 7203,6758")
    parser.add_argument("--lookback-days", type=int, default=450, help="How many days back to scan EDINET's daily index")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    try:
        client = EdinetClient()
        # Fail fast and loud if the key is missing/invalid, before scanning.
        client.list_filings_for_date(__import__("datetime").date.today())
    except EdinetAuthError as exc:
        logger.error("%s", exc)
        return 1

    existing: dict = {}
    if args.output.exists():
        with open(args.output, "r", encoding="utf-8") as f:
            for row in json.load(f):
                existing[row["id"]] = row

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    ingested = 0
    for ticker in tickers:
        try:
            article = ingest_ticker(client, ticker, args.lookback_days)
        except EdinetAuthError as exc:
            logger.error("%s", exc)
            return 1
        if article:
            existing[article["id"]] = article
            ingested += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(list(existing.values()), f, ensure_ascii=False, indent=2)

    logger.info("Ingested %d/%d ticker(s). Wrote %d total article(s) to %s", ingested, len(tickers), len(existing), args.output)
    logger.info("Restart the API server (or rely on --reload) to pick up the new corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
