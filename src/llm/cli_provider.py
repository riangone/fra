"""Local CLI-backed LLM invocation — no API keys, no network SDKs.

Mirrors the single-shot subprocess pattern documented for AiChatApp's
CliExecutorService: each request spawns a fresh CLI process, the prompt is
delivered to it (via stdin or as an argument, depending on the provider's
own conventions), and stdout is captured as the completion. There is no
process pooling / pre-warming here — this synthesis path is low-QPS and a
cold start (a few seconds for claude/antigravity, up to a few minutes for
opencode's free-tier model) is acceptable.

Supported providers, tried in order until one returns a non-empty
completion (a local, API-key-free fallback chain — analogous to
AiSettings.DefaultProvider / FallbackProvider in AiChatApp). Default order
(see config/settings.py::local_cli_provider_order, overridable via
LOCAL_CLI_PROVIDER_ORDER) puts opencode first since it is a genuinely free
model with no subscription attached, ahead of the paid-plan CLIs:

    opencode    -> `opencode run "<prompt>" --format json` (NDJSON event stream)
    claude      -> `claude -p --restricted ... --output-format text` (stdin)
    antigravity -> `antigravity --print "<prompt>" --output-format text --sandbox`

Any provider that is missing from PATH, times out, exits non-zero, or
returns empty output is skipped; if every provider fails, `invoke_local_cli`
returns None and the caller is expected to fall back to a deterministic,
non-LLM code path.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

# Tools intentionally denied for `claude -p`: this call site only ever needs
# plain text generation grounded in a prompt we already built ourselves, so
# there is no legitimate reason for the subprocess to touch the filesystem,
# shell, or network. `--restricted` additionally strips Bash/PowerShell/REPL
# at the CLI level; the explicit deny-list is defense in depth.
_CLAUDE_DISALLOWED_TOOLS = "Bash Read Write Edit Glob Grep WebFetch WebSearch Task"


class CliProviderError(RuntimeError):
    """A single provider invocation failed (non-zero exit / empty output)."""


@dataclass
class CliCompletion:
    text: str
    provider: str
    duration_ms: float


def _run_claude(prompt: str, system_prompt: str, timeout: int) -> str:
    cmd = [
        "claude",
        "-p",
        "--restricted",
        "--disallowedTools",
        _CLAUDE_DISALLOWED_TOOLS,
        "--output-format",
        "text",
    ]
    if system_prompt:
        cmd += ["--system-prompt", system_prompt]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise CliProviderError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    text = proc.stdout.strip()
    if not text:
        raise CliProviderError("claude returned empty output")
    return text


def _run_antigravity(prompt: str, system_prompt: str, timeout: int) -> str:
    # antigravity's -p/--print takes the prompt inline (not via stdin), so
    # there is no dedicated --system-prompt flag to lean on here.
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    cmd = ["antigravity", "--print", full_prompt, "--output-format", "text", "--sandbox"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise CliProviderError(f"antigravity exited {proc.returncode}: {proc.stderr[:500]}")
    text = proc.stdout.strip()
    if not text:
        # Known failure mode (see project memory): quota exhaustion exits 0
        # with empty stdout instead of raising an error.
        raise CliProviderError("antigravity returned empty output (possible quota exhaustion)")
    return text


def _run_opencode(prompt: str, system_prompt: str, timeout: int) -> str:
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    cmd = ["opencode", "run", full_prompt, "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise CliProviderError(f"opencode exited {proc.returncode}: {proc.stderr[:500]}")

    pieces: List[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = event.get("part") or {}
        if event.get("type") == "text" and part.get("type") == "text":
            pieces.append(part.get("text", ""))
    text = "".join(pieces).strip()
    if not text:
        raise CliProviderError("opencode produced no text events")
    return text


_RUNNERS: Dict[str, Callable[[str, str, int], str]] = {
    "claude": _run_claude,
    "antigravity": _run_antigravity,
    "opencode": _run_opencode,
}

_DEFAULT_TIMEOUTS: Dict[str, int] = {
    "claude": 60,
    "antigravity": 120,
    "opencode": 240,
}


def invoke_local_cli(
    prompt: str,
    system_prompt: str = "",
    provider_order: Optional[List[str]] = None,
) -> Optional[CliCompletion]:
    """Try each local AI CLI in order; return the first non-empty completion.

    Returns None if every configured provider fails, so callers can degrade
    to a deterministic non-LLM path instead of raising.
    """
    order = provider_order if provider_order is not None else settings.local_cli_provider_order
    for name in order:
        runner = _RUNNERS.get(name)
        if runner is None:
            logger.warning("synthesizer: unknown local CLI provider '%s', skipping", name)
            continue

        timeout = settings.local_cli_timeouts.get(name, _DEFAULT_TIMEOUTS.get(name, 120))
        start = time.time()
        try:
            text = runner(prompt, system_prompt, timeout)
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.info("synthesizer: local CLI '%s' succeeded in %.0fms", name, duration_ms)
            return CliCompletion(text=text, provider=name, duration_ms=duration_ms)
        except subprocess.TimeoutExpired:
            logger.warning("synthesizer: local CLI '%s' timed out after %ss", name, timeout)
        except FileNotFoundError:
            logger.warning("synthesizer: local CLI '%s' not found on PATH", name)
        except CliProviderError as exc:
            logger.warning("synthesizer: local CLI '%s' failed: %s", name, exc)
        except Exception as exc:  # defensive — a bad CLI must never crash the graph
            logger.warning("synthesizer: local CLI '%s' raised unexpected error: %s", name, exc)
    return None
