"""Unit tests for src/llm/cloud_provider.py (Azure OpenAI / Vertex AI).

All SDK calls are mocked or monkeypatched — these tests never make a real
network request, so they stay fast and deterministic in CI. Mirrors the
structure of tests/test_cli_provider.py.
"""

from types import SimpleNamespace

import pytest

from src.llm import cloud_provider


def test_invoke_azure_openai_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_api_key", "")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_endpoint", "")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_deployment", "")

    with pytest.raises(cloud_provider.CloudProviderError, match="not configured"):
        cloud_provider._invoke_azure_openai("q", "", timeout=10)


def test_invoke_azure_openai_calls_sdk_with_expected_shape(monkeypatch):
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_api_key", "key123")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_deployment", "gpt-4o-mini-deploy")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_api_version", "2024-10-21")

    captured = {}

    class FakeChatCompletions:
        def create(self, model, messages):
            captured["model"] = model
            captured["messages"] = messages
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="回答本文"))])

    class FakeChat:
        completions = FakeChatCompletions()

    class FakeAzureOpenAI:
        def __init__(self, api_key, azure_endpoint, api_version, timeout):
            captured["api_key"] = api_key
            captured["azure_endpoint"] = azure_endpoint
            captured["api_version"] = api_version
            self.chat = FakeChat()

    import types
    fake_openai_module = types.ModuleType("openai")
    fake_openai_module.AzureOpenAI = FakeAzureOpenAI
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai_module)

    text = cloud_provider._invoke_azure_openai("質問プロンプト", "システムプロンプト", timeout=30)

    assert text == "回答本文"
    assert captured["model"] == "gpt-4o-mini-deploy"
    assert captured["messages"][0] == {"role": "system", "content": "システムプロンプト"}
    assert captured["messages"][1] == {"role": "user", "content": "質問プロンプト"}
    assert captured["azure_endpoint"] == "https://example.openai.azure.com"


def test_invoke_azure_openai_raises_on_empty_completion(monkeypatch):
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_api_key", "key123")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(cloud_provider.settings, "azure_openai_deployment", "deploy")

    class FakeChatCompletions:
        def create(self, model, messages):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="   "))])

    class FakeChat:
        completions = FakeChatCompletions()

    class FakeAzureOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import types
    fake_openai_module = types.ModuleType("openai")
    fake_openai_module.AzureOpenAI = FakeAzureOpenAI
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai_module)

    with pytest.raises(cloud_provider.CloudProviderError, match="empty"):
        cloud_provider._invoke_azure_openai("q", "", timeout=10)


def test_invoke_vertex_ai_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(cloud_provider.settings, "vertex_project_id", "")

    with pytest.raises(cloud_provider.CloudProviderError, match="not configured"):
        cloud_provider._invoke_vertex_ai("q", "", timeout=10)


def test_invoke_vertex_ai_calls_sdk_with_expected_shape(monkeypatch):
    monkeypatch.setattr(cloud_provider.settings, "vertex_project_id", "my-gcp-project")
    monkeypatch.setattr(cloud_provider.settings, "vertex_location", "asia-northeast1")
    monkeypatch.setattr(cloud_provider.settings, "vertex_model", "gemini-1.5-pro")

    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(text="回答本文")

    class FakeClient:
        def __init__(self, vertexai, project, location):
            captured["vertexai"] = vertexai
            captured["project"] = project
            captured["location"] = location
            self.models = FakeModels()

    import types
    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = FakeClient
    fake_types_module = types.ModuleType("google.genai.types")
    fake_types_module.GenerateContentConfig = lambda system_instruction=None: {
        "system_instruction": system_instruction
    }
    fake_google_module = types.ModuleType("google")
    fake_google_module.genai = fake_genai_module

    import sys
    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types_module)

    text = cloud_provider._invoke_vertex_ai("質問プロンプト", "システムプロンプト", timeout=30)

    assert text == "回答本文"
    assert captured["model"] == "gemini-1.5-pro"
    assert captured["project"] == "my-gcp-project"
    assert captured["vertexai"] is True


def test_invoke_cloud_llm_falls_back_through_provider_chain(monkeypatch):
    calls = []

    def failing_azure(prompt, system_prompt, timeout):
        calls.append("azure_openai")
        raise cloud_provider.CloudProviderError("not configured")

    def succeeding_vertex(prompt, system_prompt, timeout):
        calls.append("vertex_ai")
        return "最終回答"

    monkeypatch.setitem(cloud_provider._RUNNERS, "azure_openai", failing_azure)
    monkeypatch.setitem(cloud_provider._RUNNERS, "vertex_ai", succeeding_vertex)

    result = cloud_provider.invoke_cloud_llm("prompt", provider_order=["azure_openai", "vertex_ai"])

    assert calls == ["azure_openai", "vertex_ai"]
    assert result is not None
    assert result.text == "最終回答"
    assert result.provider == "vertex_ai"


def test_invoke_cloud_llm_returns_none_when_order_empty():
    result = cloud_provider.invoke_cloud_llm("prompt", provider_order=[])
    assert result is None


def test_invoke_cloud_llm_returns_none_when_all_providers_fail(monkeypatch):
    def always_fails(prompt, system_prompt, timeout):
        raise cloud_provider.CloudProviderError("nope")

    monkeypatch.setitem(cloud_provider._RUNNERS, "azure_openai", always_fails)

    result = cloud_provider.invoke_cloud_llm("prompt", provider_order=["azure_openai"])

    assert result is None


def test_invoke_cloud_llm_survives_unexpected_exception(monkeypatch):
    def raises_weird_error(prompt, system_prompt, timeout):
        raise ValueError("something unexpected")

    def succeeds(prompt, system_prompt, timeout):
        return "recovered"

    monkeypatch.setitem(cloud_provider._RUNNERS, "azure_openai", raises_weird_error)
    monkeypatch.setitem(cloud_provider._RUNNERS, "vertex_ai", succeeds)

    result = cloud_provider.invoke_cloud_llm("prompt", provider_order=["azure_openai", "vertex_ai"])

    assert result is not None
    assert result.text == "recovered"
