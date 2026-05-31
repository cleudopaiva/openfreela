from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openfreela.ai_request_logger import AIRequestLog, AIRequestLogger
from openfreela.http_client_errors import (
    http_error_reason,
    load_response_json,
    read_http_error_body,
    trim_error_body,
)

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class OpenAIClient:
    """Small HTTP client for OpenAI chat completions.

    Example:
        client = OpenAIClient("https://api.openai.com/v1", "gpt-4o-mini", "token")
    """

    base_url: str
    model: str
    api_key: str
    timeout_seconds: int = 300
    logger: AIRequestLogger | None = None

    def chat_json(self, prompt: str) -> str:
        """Send a prompt to OpenAI and return assistant JSON content.

        Example:
            content = client.chat_json("Return JSON")
        """
        started_at = time.monotonic()
        try:
            response = post_openai_json(
                self.chat_url(),
                self.request_payload(prompt),
                self.api_key,
                self.timeout_seconds,
            )
            content = response_message_content(response)
        except (ConnectionError, ValueError) as error:
            self.log_request(prompt, "", started_at, "error", str(error))
            raise
        self.log_request(prompt, content, started_at, "ok", "")
        return content

    def chat_url(self) -> str:
        """Return the OpenAI chat completions endpoint URL.

        Example:
            url = client.chat_url()
        """
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def request_payload(self, prompt: str) -> dict[str, object]:
        """Return the OpenAI JSON request payload.

        Example:
            payload = client.request_payload("Hello")
        """
        return {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }

    def log_request(
        self, prompt: str, content: str, started_at: float, status: str, error: str
    ) -> None:
        """Record safe OpenAI request metadata when a logger is configured.

        Example:
            client.log_request("prompt", "{}", started_at, "ok", "")
        """
        if self.logger is None:
            return
        entry = AIRequestLog(
            "openai",
            self.model,
            self.base_url,
            len(prompt),
            len(content),
            time.monotonic() - started_at,
            status,
            error,
        )
        self.logger.record(entry)


def post_openai_json(
    url: str, payload: dict[str, object], api_key: str, timeout_seconds: int
) -> dict[str, object]:
    """Post JSON to OpenAI and return a decoded response object.

    Example:
        response = post_openai_json(url, {}, "token", 10)
    """
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = load_response_json(response.read(), "OpenAI response", url)
    except TimeoutError as error:
        message = (
            f"OpenAI timed out after {timeout_seconds}s while evaluating a project."
        )
        raise ConnectionError(message) from error
    except HTTPError as error:
        raise ConnectionError(openai_http_error_message(error)) from error
    except URLError as error:
        message = f"Could not reach OpenAI at {url}: {error.reason!r}."
        raise ConnectionError(message) from error
    return object_json(decoded, "OpenAI response")


def openai_http_error_message(error: HTTPError) -> str:
    """Return an actionable OpenAI HTTP error message.

    Example:
        message = openai_http_error_message(error)
    """
    body = read_http_error_body(error)
    detail = openai_error_detail(body)
    if not detail:
        detail = (
            f"Response body: {trim_error_body(body)}" if body else "No response body."
        )
    return (
        f"OpenAI request failed with HTTP {error.code} "
        f"{http_error_reason(error)}: {detail}"
    )


def openai_error_detail(body: str) -> str:
    """Return OpenAI's structured error detail when present.

    Example:
        detail = openai_error_detail('{"error": {"message": "bad"}}')
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    parts = openai_error_parts(error)
    return " ".join(parts)


def openai_error_parts(error: dict[object, object]) -> list[str]:
    """Return readable OpenAI error parts.

    Example:
        parts = openai_error_parts({"message": "bad", "type": "invalid_request"})
    """
    parts: list[str] = []
    message = error.get("message")
    if isinstance(message, str) and message:
        parts.append(message)
    error_type = error.get("type")
    if isinstance(error_type, str) and error_type:
        parts.append(f"type={error_type}")
    code = error.get("code")
    if isinstance(code, str) and code:
        parts.append(f"code={code}")
    return parts


def response_message_content(response: dict[str, object]) -> str:
    """Extract assistant message content from an OpenAI response.

    Example:
        content = response_message_content(response)
    """
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Invalid OpenAI response choices; expected non-empty list.")
    choice = object_json(choices[0], "OpenAI response choice")
    message = object_json(choice.get("message"), "OpenAI response message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError(
            "Invalid OpenAI response content; "
            "expected string at choices[0].message.content."
        )
    return content


def object_json(value: object, label: str) -> dict[str, object]:
    """Validate that a decoded JSON value is an object.

    Example:
        obj = object_json({}, "response")
    """
    if isinstance(value, dict):
        return value
    message = f"Invalid {label}; expected JSON object, got {type(value).__name__}."
    raise ValueError(message)
