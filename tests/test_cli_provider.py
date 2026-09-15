"""Unit tests for src/llm/cli_provider.py (local AI CLI invocation).

All subprocess calls are mocked — these tests never spawn a real claude /
antigravity / opencode process, so they stay fast and deterministic in CI.
"""

import subprocess
from types import SimpleNamespace

import pytest

from src.llm import cli_provider


def _completed(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_claude_builds_restricted_command_and_pipes_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, input=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["input"] = input
        captured["timeout"] = timeout
        return _completed(stdout="生成されたレポート本文")

    monkeypatch.setattr(cli_provider.subprocess, "run", fake_run)

    text = cli_provider._run_claude("質問プロンプト", "システムプロンプト", timeout=42)

    assert text == "生成されたレポート本文"
    assert captured["input"] == "質問プロンプト"
    assert captured["timeout"] == 42
    assert captured["cmd"][0] == "claude"
    assert "--restricted" in captured["cmd"]
    assert "--system-prompt" in captured["cmd"]
    assert "システムプロンプト" in captured["cmd"]
    assert "--disallowedTools" in captured["cmd"]


def test_run_claude_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        cli_provider.subprocess, "run", lambda *a, **k: _completed(returncode=1, stderr="boom")
    )
    with pytest.raises(cli_provider.CliProviderError):
        cli_provider._run_claude("q", "", timeout=10)


def test_run_claude_raises_on_empty_output(monkeypatch):
    monkeypatch.setattr(cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout="   "))
    with pytest.raises(cli_provider.CliProviderError):
        cli_provider._run_claude("q", "", timeout=10)


def test_run_antigravity_passes_prompt_as_argument(monkeypatch):
    captured = {}

    def fake_run(cmd, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        return _completed(stdout="PONG")

    monkeypatch.setattr(cli_provider.subprocess, "run", fake_run)

    text = cli_provider._run_antigravity("質問", "システム", timeout=10)

    assert text == "PONG"
    assert captured["cmd"][0] == "antigravity"
    assert "--print" in captured["cmd"]
    # prompt is an inline argument (not stdin) — must contain both system + user text
    prompt_arg = captured["cmd"][captured["cmd"].index("--print") + 1]
    assert "システム" in prompt_arg
    assert "質問" in prompt_arg
    assert "--sandbox" in captured["cmd"]


def test_run_antigravity_empty_output_treated_as_quota_failure(monkeypatch):
    monkeypatch.setattr(cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout=""))
    with pytest.raises(cli_provider.CliProviderError, match="quota"):
        cli_provider._run_antigravity("q", "", timeout=10)


def test_run_opencode_parses_ndjson_text_events(monkeypatch):
    ndjson = "\n".join([
        '{"type":"step_start","part":{"type":"step-start"}}',
        '{"type":"text","part":{"type":"text","text":"PONG"}}',
        '{"type":"step_finish","part":{"type":"step-finish"}}',
    ])
    monkeypatch.setattr(cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout=ndjson))

    text = cli_provider._run_opencode("q", "", timeout=10)

    assert text == "PONG"


def test_run_opencode_concatenates_multiple_text_events(monkeypatch):
    ndjson = "\n".join([
        '{"type":"text","part":{"type":"text","text":"foo"}}',
        '{"type":"text","part":{"type":"text","text":"bar"}}',
    ])
    monkeypatch.setattr(cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout=ndjson))

    assert cli_provider._run_opencode("q", "", timeout=10) == "foobar"


def test_run_opencode_ignores_malformed_lines(monkeypatch):
    ndjson = "not json\n" + '{"type":"text","part":{"type":"text","text":"ok"}}'
    monkeypatch.setattr(cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout=ndjson))

    assert cli_provider._run_opencode("q", "", timeout=10) == "ok"


def test_run_opencode_raises_when_no_text_events(monkeypatch):
    monkeypatch.setattr(
        cli_provider.subprocess, "run", lambda *a, **k: _completed(stdout='{"type":"step_start"}')
    )
    with pytest.raises(cli_provider.CliProviderError):
        cli_provider._run_opencode("q", "", timeout=10)


def test_invoke_local_cli_falls_back_through_provider_chain(monkeypatch):
    calls = []

    def failing_claude(prompt, system_prompt, timeout):
        calls.append("claude")
        raise cli_provider.CliProviderError("down")

    def timing_out_antigravity(prompt, system_prompt, timeout):
        calls.append("antigravity")
        raise subprocess.TimeoutExpired(cmd="antigravity", timeout=timeout)

    def succeeding_opencode(prompt, system_prompt, timeout):
        calls.append("opencode")
        return "最終回答"

    monkeypatch.setitem(cli_provider._RUNNERS, "claude", failing_claude)
    monkeypatch.setitem(cli_provider._RUNNERS, "antigravity", timing_out_antigravity)
    monkeypatch.setitem(cli_provider._RUNNERS, "opencode", succeeding_opencode)

    result = cli_provider.invoke_local_cli("prompt", provider_order=["claude", "antigravity", "opencode"])

    assert calls == ["claude", "antigravity", "opencode"]
    assert result is not None
    assert result.text == "最終回答"
    assert result.provider == "opencode"


def test_invoke_local_cli_returns_none_when_all_providers_fail(monkeypatch):
    def always_fails(prompt, system_prompt, timeout):
        raise cli_provider.CliProviderError("nope")

    monkeypatch.setitem(cli_provider._RUNNERS, "claude", always_fails)

    result = cli_provider.invoke_local_cli("prompt", provider_order=["claude"])

    assert result is None


def test_invoke_local_cli_skips_unknown_provider_name(monkeypatch):
    def succeeds(prompt, system_prompt, timeout):
        return "ok"

    monkeypatch.setitem(cli_provider._RUNNERS, "claude", succeeds)

    result = cli_provider.invoke_local_cli("prompt", provider_order=["totally-unknown", "claude"])

    assert result is not None
    assert result.provider == "claude"


def test_invoke_local_cli_survives_unexpected_exception(monkeypatch):
    def raises_weird_error(prompt, system_prompt, timeout):
        raise ValueError("something unexpected")

    def succeeds(prompt, system_prompt, timeout):
        return "recovered"

    monkeypatch.setitem(cli_provider._RUNNERS, "claude", raises_weird_error)
    monkeypatch.setitem(cli_provider._RUNNERS, "antigravity", succeeds)

    result = cli_provider.invoke_local_cli("prompt", provider_order=["claude", "antigravity"])

    assert result is not None
    assert result.text == "recovered"
