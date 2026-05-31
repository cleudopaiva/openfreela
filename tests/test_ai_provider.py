from __future__ import annotations

from pathlib import Path

import pytest

from openfreela.ai_provider import AIProviderOptions, ai_client_from_options
from openfreela.ollama_client import OllamaClient
from openfreela.openai_client import DEFAULT_OPENAI_BASE_URL, OpenAIClient


def test_ai_client_from_options_defaults_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    client = ai_client_from_options(AIProviderOptions("ollama", True, Path("x.jsonl")))

    assert isinstance(client, OllamaClient)
    assert client.logger is not None


def test_ai_client_from_options_builds_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "token")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")

    client = ai_client_from_options(AIProviderOptions("openai"))

    assert isinstance(client, OpenAIClient)
    assert client.model == "gpt-4o-mini"
    assert client.base_url == DEFAULT_OPENAI_BASE_URL


def test_ai_client_from_options_requires_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_client_from_options(AIProviderOptions("openai"))


def test_ai_client_from_options_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        ai_client_from_options(AIProviderOptions("bad"))
