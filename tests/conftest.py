"""Shared pytest fixtures.

The synthesizer's default backend (`settings.llm_backend == "local_cli"`)
shells out to a real, locally installed AI CLI (claude / antigravity /
opencode — see src/llm/cli_provider.py). That is the right default for the
running service, but the test suite must stay fast, deterministic, and free
of external process dependencies (no CLI auth/quota available in CI).

This autouse fixture forces the deterministic template backend for every
test by default. Tests that specifically want to exercise the local_cli
code path (see tests/test_local_cli_synthesis.py) mock
`src.llm.cli_provider.invoke_local_cli` and opt back into "local_cli"
explicitly — they never spawn a real subprocess either.
"""

import pytest

from config.settings import settings


@pytest.fixture(autouse=True)
def _deterministic_llm_backend():
    original = settings.llm_backend
    settings.llm_backend = "template"
    yield
    settings.llm_backend = original
