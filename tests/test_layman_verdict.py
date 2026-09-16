"""Tests for the deterministic, rule-based layman verdict section appended
to every synthesized report (see `_build_layman_verdict_section` in
`src/graph/nodes/synthesizer.py`).

This section exists so a non-specialist reader gets a plain "buy / hold /
caution" style takeaway at the end of the report, without letting the LLM
freely hallucinate an investment call. It must therefore:
  - be derived only from fields already present in `financial_metrics`
    (valuation_status, roe_percent) — never invent new judgments,
  - always cite the same `mcp_val_<ticker>` id the metrics themselves use,
  - always carry the "not investment advice" disclaimer,
  - respect `target_tickers` filtering like the rest of the report,
  - be a no-op (empty string) when there are no valuation metrics at all
    (e.g. macro-only or disclosure-only queries).
"""

from src.graph.nodes.synthesizer import _build_layman_verdict_section, synthesizer_node
from config.settings import settings


def _metric(ticker="7203", company_name="トヨタ自動車", valuation_status="FAIR", roe_percent=8.0):
    return {
        "ticker": ticker,
        "company_name": company_name,
        "per": 12.0,
        "pbr": 1.1,
        "roe_percent": roe_percent,
        "tsr_percent": 20.0,
        "valuation_status": valuation_status,
    }


def test_undervalued_with_good_roe_yields_bullish_label():
    section = _build_layman_verdict_section([_metric(valuation_status="UNDERVALUED", roe_percent=13.8)])
    assert "買い" in section
    assert "[mcp_val_7203]" in section


def test_overvalued_yields_cautious_label():
    section = _build_layman_verdict_section([_metric(valuation_status="OVERVALUED", roe_percent=8.0)])
    assert "慎重" in section
    assert "[mcp_val_7203]" in section


def test_fair_yields_wait_and_see_label():
    section = _build_layman_verdict_section([_metric(valuation_status="FAIR", roe_percent=8.0)])
    assert "様子見" in section


def test_disclaimer_always_present():
    section = _build_layman_verdict_section([_metric()])
    assert "投資助言" in section
    assert "ご自身の責任" in section


def test_respects_target_ticker_filter():
    metrics = [_metric(ticker="7203"), _metric(ticker="6758", company_name="ソニーグループ")]
    section = _build_layman_verdict_section(metrics, target_tickers=["6758"])
    assert "7203" not in section
    assert "6758" in section


def test_empty_when_no_valuation_metrics():
    # Disclosure-only metric (no per/pbr) must not produce a verdict line.
    disclosure_only = [{"ticker": "7203", "company_name": "トヨタ自動車", "revenue_billion_jpy": 100.0}]
    assert _build_layman_verdict_section(disclosure_only) == ""
    assert _build_layman_verdict_section([]) == ""


def test_synthesizer_node_appends_verdict_regardless_of_backend():
    settings.llm_backend = "template"
    try:
        state = {
            "query": "トヨタの業績は？",
            "retrieved_chunks": [],
            "financial_metrics": [_metric(valuation_status="UNDERVALUED", roe_percent=13.8)],
            "target_tickers": ["7203"],
            "retry_count": 0,
            "execution_trace": [],
        }
        result = synthesizer_node(state)
        assert "まとめ：一般の方向けの参考結論" in result["draft_response"]
        assert result["draft_response"] == result["final_response"]
    finally:
        settings.llm_backend = "template"
