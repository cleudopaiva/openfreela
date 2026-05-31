from __future__ import annotations

import json
from email.message import Message
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError

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


def test_post_openai_json_reports_structured_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps(
        {
            "error": {
                "message": "Incorrect API key provided.",
                "type": "invalid_request_error",
                "code": "invalid_api_key",
            }
        }
    )

    def fail_with_http_error(request: Request, *, timeout: int) -> object:
        raise HTTPError(
            request.full_url, 401, "Unauthorized", Message(), BytesIO(body.encode())
        )

    monkeypatch.setattr(openai_client, "urlopen", fail_with_http_error)

    with pytest.raises(ConnectionError) as error:
        post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 12)

    message = str(error.value)
    assert "OpenAI request failed with HTTP 401 Unauthorized" in message
    assert "Incorrect API key provided." in message
    assert "type=invalid_request_error" in message
    assert "code=invalid_api_key" in message


def test_post_openai_json_reports_plain_http_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_http_error(request: Request, *, timeout: int) -> object:
        raise HTTPError(
            request.full_url,
            500,
            "Server Error",
            Message(),
            BytesIO(b"bad gateway"),
        )

    monkeypatch.setattr(openai_client, "urlopen", fail_with_http_error)

    with pytest.raises(ConnectionError, match="Response body: bad gateway"):
        post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 12)


def test_post_openai_json_reports_transport_error_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_with_url_error(request: Request, *, timeout: int) -> object:
        raise URLError("network unreachable")

    monkeypatch.setattr(openai_client, "urlopen", fail_with_url_error)

    with pytest.raises(ConnectionError, match="network unreachable"):
        post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 12)


def test_post_openai_json_reports_invalid_success_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InvalidJSONResponse:
        def __enter__(self) -> InvalidJSONResponse:
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            pass

        def read(self) -> bytes:
            return b"not json"

    def fake_urlopen(request: Request, *, timeout: int) -> InvalidJSONResponse:
        return InvalidJSONResponse()

    monkeypatch.setattr(openai_client, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="Invalid OpenAI response from"):
        post_openai_json("https://api.openai.com/v1/chat/completions", {}, "token", 12)
