"""Integration tests for the synthesizer node's local-CLI LLM path.

`invoke_local_cli` is mocked throughout — these tests verify the wiring
(prompt grounding, provider tagging in execution_trace, graceful fallback
to the deterministic template) without spawning a real CLI subprocess.
"""

from config.settings import settings
from src.graph.nodes import synthesizer
from src.llm.cli_provider import CliCompletion


def _sample_chunks():
    """Static news chunks. Kept only to prove the synthesizer ignores them —
    grounding now comes exclusively from Live financial_metrics (see
    _build_grounding_context's NOTE)."""
    return [
        {
            "id": "doc_nikkei_6758_01",
            "title": "ソニーグループ決算記事",
            "content": "ソニーグループの2024年3月期営業利益は1兆2000億円となった。",
            "ticker": "6758",
        }
    ]


def _sample_metrics():
    return [
        {
            "ticker": "6758",
            "company_name": "ソニーグループ",
            "per": 18.2,
            "pbr": 2.1,
            "roe_percent": 11.5,
            "tsr_percent": 8.4,
            "valuation_status": "FAIR",
        }
    ]


def test_local_cli_backend_used_when_enabled(monkeypatch):
    settings.llm_backend = "local_cli"
    try:
        captured_prompt = {}

        def fake_invoke(prompt, system_prompt=""):
            captured_prompt["prompt"] = prompt
            captured_prompt["system_prompt"] = system_prompt
            return CliCompletion(
                text="### 財務・業績分析レポート\nソニーグループのPERは18.2倍だった [mcp_val_6758]。",
                provider="claude",
                duration_ms=123.0,
            )

        monkeypatch.setattr(synthesizer, "invoke_local_cli", fake_invoke)

        state = {
            "query": "ソニーの業績は？",
            "retrieved_chunks": _sample_chunks(),
            "financial_metrics": _sample_metrics(),
            "target_tickers": ["6758"],
            "retry_count": 0,
            "execution_trace": [],
        }

        result = synthesizer.synthesizer_node(state)

        assert "mcp_val_6758" in result["draft_response"]
        assert result["draft_response"] == result["final_response"]
        # Live metrics are grounded in the prompt; static news chunks are not.
        assert "mcp_val_6758" in captured_prompt["prompt"]
        assert "doc_nikkei_6758_01" not in captured_prompt["prompt"]
        assert "ソニーの業績は？" in captured_prompt["prompt"]
        trace_entry = result["execution_trace"][-1]
        assert trace_entry["llm_provider"] == "claude"
    finally:
        settings.llm_backend = "template"


def test_falls_back_to_template_when_all_cli_providers_fail(monkeypatch):
    settings.llm_backend = "local_cli"
    try:
        monkeypatch.setattr(synthesizer, "invoke_local_cli", lambda prompt, system_prompt="": None)

        state = {
            "query": "ソニーの業績は？",
            "retrieved_chunks": _sample_chunks(),
            "financial_metrics": _sample_metrics(),
            "target_tickers": ["6758"],
            "retry_count": 0,
            "execution_trace": [],
        }

        result = synthesizer.synthesizer_node(state)

        # deterministic template path must still produce a valid, cited draft
        # based on Live metrics only — never the static news chunk.
        assert "[mcp_val_6758]" in result["draft_response"]
        assert "doc_nikkei_6758_01" not in result["draft_response"]
        assert result["execution_trace"][-1]["llm_provider"] == "template"
    finally:
        settings.llm_backend = "template"


def test_falls_back_to_template_when_cli_call_raises(monkeypatch):
    settings.llm_backend = "local_cli"
    try:
        def boom(prompt, system_prompt=""):
            raise RuntimeError("unexpected CLI crash")

        monkeypatch.setattr(synthesizer, "invoke_local_cli", boom)

        state = {
            "query": "ソニーの業績は？",
            "retrieved_chunks": _sample_chunks(),
            "financial_metrics": _sample_metrics(),
            "target_tickers": ["6758"],
            "retry_count": 0,
            "execution_trace": [],
        }

        result = synthesizer.synthesizer_node(state)

        assert result["draft_response"]  # graph must never crash
        assert result["execution_trace"][-1]["llm_provider"] == "template"
    finally:
        settings.llm_backend = "template"


def test_template_backend_never_calls_local_cli(monkeypatch):
    settings.llm_backend = "template"

    def should_not_be_called(prompt, system_prompt=""):
        raise AssertionError("invoke_local_cli must not be called when llm_backend == 'template'")

    monkeypatch.setattr(synthesizer, "invoke_local_cli", should_not_be_called)

    state = {
        "query": "ソニーの業績は？",
        "retrieved_chunks": _sample_chunks(),
        "financial_metrics": _sample_metrics(),
        "target_tickers": ["6758"],
        "retry_count": 0,
        "execution_trace": [],
    }

    result = synthesizer.synthesizer_node(state)
    assert result["execution_trace"][-1]["llm_provider"] == "template"


def test_no_context_returns_none_from_local_llm_helper():
    assert synthesizer.synthesize_via_local_llm("q", [], []) is None


def test_news_chunks_alone_produce_no_grounding():
    """Static news chunks with no Live metrics must not be synthesized —
    only Live data may drive the report."""
    assert synthesizer.synthesize_via_local_llm("q", _sample_chunks(), []) is None
