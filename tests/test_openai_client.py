from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openfreela import openai_client
from openfreela.openai_client import (
    OpenAIClient,
    post_openai_json,
    response_message_content,
)

if TYPE_CHECKING:
    from urllib.request import Request


class FakeHTTPResponse:
    """Fake urllib response object for OpenAI client tests.

    Example:
        response = FakeHTTPResponse({"choices": []})
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


def test_openai_client_builds_chat_url_and_payload() -> None:
    client = OpenAIClient("https://api.openai.com/v1/", "gpt-4o-mini", "token")

    assert client.chat_url() == "https://api.openai.com/v1/chat/completions"
    assert client.request_payload("hello")["model"] == "gpt-4o-mini"
    assert client.request_payload("hello")["response_format"] == {"type": "json_object"}


def test_post_openai_json_sends_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: int) -> FakeHTTPResponse:
        requests.append(request)
        return FakeHTTPResponse({"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(openai_client, "urlopen", fake_urlopen)

    post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 10)

    assert requests[0].get_header("Authorization") == "Bearer token"
    assert requests[0].get_header("Content-type") == "application/json"


def test_response_message_content_extracts_openai_content() -> None:
    content = response_message_content(
        {"choices": [{"message": {"content": '{"ok": true}'}}]}
    )

    assert content == '{"ok": true}'


def test_post_openai_json_converts_timeout_to_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_timeout(request: Request, *, timeout: int) -> object:
        raise TimeoutError("timed out")

    monkeypatch.setattr(openai_client, "urlopen", fail_with_timeout)

    with pytest.raises(ConnectionError, match="timed out after 12s"):
        post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 12)
