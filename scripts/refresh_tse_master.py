#!/usr/bin/env python3
"""Refresh data/tse_listed_companies.csv from JPX's official listed-company master.

Downloads "東証上場銘柄一覧" (data_j.xlsx) from JPX, keeps only real equities
(Prime/Standard/Growth, domestic + foreign stock — excludes ETF/ETN, REIT/funds,
PRO Market, and investment certificates), and writes code/name/market/sector
columns to data/tse_listed_companies.csv.

This file backs src/mcp_server/tools/tse_master.py, which resolves Japanese
kanji company names to ticker codes locally (no network) — closing a gap where
yfinance's search API cannot resolve kanji queries at all.

Usage:
    python scripts/refresh_tse_master.py

No third-party dependencies: .xlsx is parsed by hand as a zip of XML (stdlib
zipfile + xml.etree) since it's a single flat sheet — not worth adding
openpyxl/pandas as a runtime dependency for this one-off refresh script.
"""

import csv
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

JPX_LISTING_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Real equities only. Excludes ETF・ETN, REIT・ベンチャーファンド・カントリー
# ファンド・インフラファンド, PRO Market (professional-investor-only, largely
# shell/pre-IPO listings), and 出資証券 (cooperative investment certificates,
# not corporate stock) — none of these are "companies" a user would ask about
# by name in a financial-research query.
INCLUDE_SEGMENTS = {
    "プライム（内国株式）",
    "スタンダード（内国株式）",
    "グロース（内国株式）",
    "プライム（外国株式）",
    "スタンダード（外国株式）",
    "グロース（外国株式）",
}

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "tse_listed_companies.csv"


def _find_xlsx_url() -> str:
    with urllib.request.urlopen(JPX_LISTING_PAGE, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    import re

    m = re.search(r'href="([^"]+data_j\.xlsx)"', html)
    if not m:
        raise RuntimeError(
            f"Could not find data_j.xlsx link on {JPX_LISTING_PAGE}; "
            "JPX may have changed their page layout."
        )
    url = m.group(1)
    if url.startswith("/"):
        url = "https://www.jpx.co.jp" + url
    return url


def _parse_xlsx_rows(xlsx_bytes: bytes) -> list[dict[str, str]]:
    z = zipfile.ZipFile(__import__("io").BytesIO(xlsx_bytes))
    shared_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    shared = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in shared_root.findall("m:si", NS)]

    sheet_root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = sheet_root.find("m:sheetData", NS).findall("m:row", NS)

    def cell_value(c):
        v = c.find("m:v", NS)
        if v is None:
            return ""
        return shared[int(v.text)] if c.get("t") == "s" else v.text

    def row_cells(r):
        cells = {}
        for c in r.findall("m:c", NS):
            col = "".join(ch for ch in c.get("r") if ch.isalpha())
            cells[col] = cell_value(c)
        return cells

    header_cells = row_cells(rows[0])
    # Columns are fixed by JPX's format: B=code, C=name, D=market, F=33-sector.
    parsed = []
    for r in rows[1:]:
        cells = row_cells(r)
        # Normalize full-width spaces (used by JPX for e.g. multi-word
        # romanized names like "Ｖｅｒｉｔａｓ　Ｉｎ　Ｓｉｌｉｃｏ") to
        # regular half-width spaces for cleaner matching/display.
        name = (cells.get("C") or "").strip().replace("　", " ")
        parsed.append(
            {
                "code": (cells.get("B") or "").strip(),
                "name": name,
                "market_segment": (cells.get("D") or "").strip(),
                "sector_33": (cells.get("F") or "").strip(),
            }
        )
    del header_cells
    return parsed


def main() -> int:
    print(f"Locating data_j.xlsx from {JPX_LISTING_PAGE} ...")
    xlsx_url = _find_xlsx_url()
    print(f"Downloading {xlsx_url} ...")
    with urllib.request.urlopen(xlsx_url, timeout=60) as resp:
        xlsx_bytes = resp.read()

    all_rows = _parse_xlsx_rows(xlsx_bytes)
    kept = [
        row
        for row in all_rows
        if row["code"] and row["name"] and row["market_segment"] in INCLUDE_SEGMENTS
    ]
    kept.sort(key=lambda r: r["code"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "market_segment", "sector_33"])
        writer.writeheader()
        writer.writerows(kept)

    print(f"Wrote {len(kept)} companies (of {len(all_rows)} total listed instruments) to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
