"""Unit tests for the EDINET ingestion client (Tier 1 corpus expansion).

No real network calls: HTTP is mocked. These tests exercise the parts that
don't require a live EDINET_API_KEY -- the CSV/XBRL fact extraction, article
composition, and the auth-error-is-loud-not-silent contract. A synthetic CSV
fixture is used to mimic EDINET's documented type=5 export format (UTF-16LE,
tab-separated, one XBRL fact per row).
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server.tools.edinet_client import (
    EdinetAuthError,
    EdinetClient,
    EdinetFilingSummary,
    _decode_edinet_csv,
    _extract_summary_facts,
    build_article_content,
)

_SAMPLE_CSV_ROWS = [
    ["要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別", "期間・時点", "ユニットID", "値"],
    [
        "jpcrp_cor:NetSalesSummaryOfBusinessResults",
        "売上高",
        "CurrentYearDuration",
        "当期",
        "連結",
        "期間",
        "JPY",
        "45095325",
    ],
    [
        "jpcrp_cor:OperatingIncomeSummaryOfBusinessResults",
        "営業利益",
        "CurrentYearDuration",
        "当期",
        "連結",
        "期間",
        "JPY",
        "5352934",
    ],
    # A prior-year row for the same element should be ignored in favor of
    # the current-year row.
    [
        "jpcrp_cor:OperatingIncomeSummaryOfBusinessResults",
        "営業利益",
        "Prior1YearDuration",
        "前期",
        "連結",
        "期間",
        "JPY",
        "2725013",
    ],
    # Unrelated element -- must not leak into extracted facts.
    ["jpcrp_cor:SomeOtherElement", "その他", "CurrentYearDuration", "当期", "連結", "期間", "JPY", "999"],
]


def _make_csv_text() -> str:
    lines = ["\t".join(row) for row in _SAMPLE_CSV_ROWS]
    return "\n".join(lines)


def test_extract_summary_facts_prefers_current_year_consolidated():
    facts = _extract_summary_facts(_make_csv_text())
    assert facts["売上高"] == "45095325"
    assert facts["営業利益"] == "5352934"  # not the prior-year 2725013
    assert "経常利益" not in facts  # absent from the fixture -> simply omitted
    assert "その他" not in facts.values()


def test_decode_edinet_csv_handles_utf16_bom():
    text = "要素ID\t値\nfoo\tbar"
    raw = text.encode("utf-16")
    assert _decode_edinet_csv(raw) == text


def test_build_article_content_omits_missing_facts_never_invents():
    summary = EdinetFilingSummary(
        doc_id="S100ABCD",
        filer_name="テスト株式会社",
        sec_code_4digit="9999",
        doc_description="有価証券報告書",
        submit_date="2024-06-27",
        period_end="2024-03-31",
        facts={"売上高": "45095325"},
    )
    content = build_article_content(summary)
    assert "テスト株式会社" in content
    assert "売上高は45095325円" in content
    assert "営業利益" not in content  # not in facts -> must not appear
    assert "EDINET" in content


def test_client_raises_loud_auth_error_without_key():
    client = EdinetClient(api_key="")
    with pytest.raises(EdinetAuthError):
        client.list_filings_for_date(__import__("datetime").date(2024, 5, 13))


def test_client_raises_loud_auth_error_on_401():
    mock_session = MagicMock()
    mock_response = MagicMock(status_code=401, text="invalid key")
    mock_session.get.return_value = mock_response
    client = EdinetClient(api_key="bad-key", session=mock_session)
    with pytest.raises(EdinetAuthError):
        client.list_filings_for_date(__import__("datetime").date(2024, 5, 13))


def test_search_filings_matches_on_4digit_prefix_of_5digit_seccode():
    mock_session = MagicMock()
    mock_response = MagicMock(status_code=200)
    mock_response.json.return_value = {
        "results": [
            {"secCode": "72030", "docTypeCode": "120", "docID": "S100XYZ", "filerName": "トヨタ自動車"},
            {"secCode": "67580", "docTypeCode": "120", "docID": "S100OTHER", "filerName": "ソニーグループ"},
        ]
    }
    mock_session.get.return_value = mock_response
    client = EdinetClient(api_key="dummy", session=mock_session)

    hits = client.search_filings("7203", lookback_days=1, max_hits=1)
    assert len(hits) == 1
    assert hits[0]["docID"] == "S100XYZ"


def test_fetch_summary_facts_reads_zip_csv():
    csv_bytes = _make_csv_text().encode("utf-16")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL_TO_CSV/jpcrp030000-asr.csv", csv_bytes)

    mock_session = MagicMock()
    mock_response = MagicMock(status_code=200, content=buf.getvalue())
    mock_session.get.return_value = mock_response
    client = EdinetClient(api_key="dummy", session=mock_session)

    facts = client.fetch_summary_facts("S100XYZ")
    assert facts["売上高"] == "45095325"
