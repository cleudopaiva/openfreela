from __future__ import annotations

from pathlib import Path

import pytest

from openfreela.ai.ollama_client import OllamaClient
from openfreela.ai.openai_client import DEFAULT_OPENAI_BASE_URL, OpenAIClient
from openfreela.ai.provider import AIProviderOptions, ai_client_from_options


def test_ai_client_from_options_defaults_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.invalid")

    client = ai_client_from_options(
        AIProviderOptions("ollama", "qwen3.5:latest", True, Path("x.jsonl"))
    )

    assert isinstance(client, OllamaClient)
    assert client.base_url == "http://example.invalid"
    assert client.model == "qwen3.5:latest"
    assert client.logger is not None


def test_ai_client_from_options_builds_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")

    client = ai_client_from_options(AIProviderOptions("openai", "gpt-4o-mini"))

    assert isinstance(client, OpenAIClient)
    assert client.model == "gpt-4o-mini"
    assert client.base_url == DEFAULT_OPENAI_BASE_URL


def test_ai_client_from_options_requires_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_client_from_options(AIProviderOptions("openai", "gpt-4o-mini"))


def test_ai_client_from_options_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        ai_client_from_options(AIProviderOptions("bad", "model"))
