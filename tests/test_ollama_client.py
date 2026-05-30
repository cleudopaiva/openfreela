from __future__ import annotations

import pytest

from openfreela.ollama_client import OllamaClient, response_message_content


def test_ollama_client_builds_chat_url_and_payload() -> None:
    client = OllamaClient("http://localhost:11434/", "qwen3.5:latest")

    assert client.chat_url() == "http://localhost:11434/api/chat"
    assert client.request_payload("hello")["model"] == "qwen3.5:latest"


def test_response_message_content_extracts_content() -> None:
    content = response_message_content({"message": {"content": "{}"}})

    assert content == "{}"


def test_response_message_content_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="expected object"):
        response_message_content({"message": "bad"})
