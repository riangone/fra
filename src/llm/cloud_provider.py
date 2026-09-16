"""Cloud LLM providers — Azure OpenAI Service / Google Vertex AI.

This module exists purely to close a JD tech-stack gap (Azure OpenAI +
Vertex AI are the first line of the Nikkei LLMアプリケーションエンジニア
posting's stack). It is intentionally NOT the primary synthesis path.

Priority is unchanged from before this module existed:

    1. local AI CLI (claude / antigravity / opencode) — `src.llm.cli_provider`,
       always tried first when `settings.llm_backend == "local_cli"`.
    2. cloud providers defined here — tried ONLY if local CLI fails/returns
       nothing AND the operator has opted in via
       `settings.llm_cloud_fallback_order` (empty by default, so this file
       has zero effect on a default install).
    3. deterministic template assembler (`synthesize_grounded_response`) —
       final, always-succeeds fallback.

Both SDKs (`openai`'s `AzureOpenAI` client, `google-genai`'s Vertex mode)
are imported lazily inside each runner so a machine without them installed
still runs the local-CLI/template path unmodified — missing SDK is treated
exactly like "provider not configured": skip, don't crash the graph.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class CloudProviderError(RuntimeError):
    """A single cloud provider invocation failed, or is not configured/installed."""


@dataclass
class CloudCompletion:
    text: str
    provider: str
    duration_ms: float


def _invoke_azure_openai(prompt: str, system_prompt: str, timeout: int) -> str:
    if not (settings.azure_openai_api_key and settings.azure_openai_endpoint and settings.azure_openai_deployment):
        raise CloudProviderError(
            "azure_openai not configured (need AZURE_OPENAI_API_KEY / "
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_DEPLOYMENT)"
        )
    try:
        from openai import AzureOpenAI
    except ImportError as exc:
        raise CloudProviderError(f"'openai' SDK not installed: {exc}") from exc

    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        timeout=timeout,
    )
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=messages,
        )
    except Exception as exc:  # openai SDK raises its own exception hierarchy
        raise CloudProviderError(f"azure_openai request failed: {exc}") from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise CloudProviderError("azure_openai returned empty completion")
    return text


def _invoke_vertex_ai(prompt: str, system_prompt: str, timeout: int) -> str:
    if not settings.vertex_project_id:
        raise CloudProviderError("vertex_ai not configured (need VERTEX_PROJECT_ID / GOOGLE_CLOUD_PROJECT)")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise CloudProviderError(f"'google-genai' SDK not installed: {exc}") from exc

    client = genai.Client(
        vertexai=True,
        project=settings.vertex_project_id,
        location=settings.vertex_location,
    )
    gen_config = types.GenerateContentConfig(system_instruction=system_prompt) if system_prompt else None

    try:
        response = client.models.generate_content(
            model=settings.vertex_model,
            contents=prompt,
            config=gen_config,
        )
    except Exception as exc:  # google-genai raises its own exception hierarchy
        raise CloudProviderError(f"vertex_ai request failed: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise CloudProviderError("vertex_ai returned empty completion")
    return text


_RUNNERS: Dict[str, Callable[[str, str, int], str]] = {
    "azure_openai": _invoke_azure_openai,
    "vertex_ai": _invoke_vertex_ai,
}


def invoke_cloud_llm(
    prompt: str,
    system_prompt: str = "",
    provider_order: Optional[List[str]] = None,
) -> Optional[CloudCompletion]:
    """Try each configured cloud provider in order; return the first success.

    Mirrors `src.llm.cli_provider.invoke_local_cli`'s contract: returns None
    (never raises) if every provider is unconfigured/unavailable/fails, so
    the caller can fall through to the next stage of the fallback chain.
    """
    order = provider_order if provider_order is not None else settings.llm_cloud_fallback_order
    timeout = settings.llm_cloud_timeout
    for name in order:
        runner = _RUNNERS.get(name)
        if runner is None:
            logger.warning("synthesizer: unknown cloud LLM provider '%s', skipping", name)
            continue

        start = time.time()
        try:
            text = runner(prompt, system_prompt, timeout)
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.info("synthesizer: cloud provider '%s' succeeded in %.0fms", name, duration_ms)
            return CloudCompletion(text=text, provider=name, duration_ms=duration_ms)
        except CloudProviderError as exc:
            # Expected/common case (not configured, SDK missing) — info, not
            # a warning, to avoid alarming logs on a default install.
            logger.info("synthesizer: cloud provider '%s' unavailable: %s", name, exc)
        except Exception as exc:  # defensive — a bad SDK call must never crash the graph
            logger.warning("synthesizer: cloud provider '%s' raised unexpected error: %s", name, exc)
    return None
