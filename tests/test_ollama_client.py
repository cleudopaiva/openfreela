from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openfreela import ollama_client
from openfreela.ai_request_logger import SafeAIRequestLogger
from openfreela.ollama_client import OllamaClient, post_json, response_message_content

if TYPE_CHECKING:
    from pathlib import Path
    from urllib.request import Request


class FakeHTTPResponse:
    """Fake urllib response object for Ollama client tests.

    Example:
        response = FakeHTTPResponse({"message": {"content": "{}"}})
    """

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeHTTPResponse:
        """Return the fake context manager response."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Exit the fake context manager."""

    def read(self) -> bytes:
        """Return the fake JSON response body."""
        return json.dumps(self.payload).encode("utf-8")


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


def test_post_json_converts_timeout_to_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_timeout(request: Request, *, timeout: int) -> object:
        raise TimeoutError("timed out")

    monkeypatch.setattr(ollama_client, "urlopen", fail_with_timeout)

    with pytest.raises(ConnectionError, match="timed out after 12s"):
        post_json("http://localhost:11434/api/chat", {}, 12)


def test_ollama_client_logs_safe_request_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "ai.jsonl"

    def fake_urlopen(request: Request, *, timeout: int) -> FakeHTTPResponse:
        return FakeHTTPResponse(
            {
                "message": {"content": '{"ok": true}'},
                "eval_count": 12,
                "total_duration": 123,
            }
        )

    monkeypatch.setattr(ollama_client, "urlopen", fake_urlopen)
    client = OllamaClient(
        "http://localhost:11434",
        "qwen3.5:latest",
        logger=SafeAIRequestLogger(True, log_path),
    )

    content = client.chat_json("Return JSON")

    assert content == '{"ok": true}'
    assert "AI response received: provider=ollama" in capsys.readouterr().out
    saved = json.loads(log_path.read_text().splitlines()[0])
    assert saved["provider"] == "ollama"
    assert saved["prompt_chars"] == 11
    assert saved["response_chars"] == 12
    assert saved["metrics"]["eval_count"] == 12
