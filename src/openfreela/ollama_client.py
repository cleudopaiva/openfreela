from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from openfreela.ai_request_logger import (
    AIRequestLog,
    AIRequestLogger,
    safe_metric_dict,
)
from openfreela.http_client_errors import (
    http_error_reason,
    load_response_json,
    read_http_error_body,
    trim_error_body,
)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_METRIC_KEYS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)


@dataclass(frozen=True)
class OllamaClient:
    """Small HTTP client for Ollama chat completions.

    Example:
        client = OllamaClient("http://localhost:11434", "qwen3.5:latest")
    """

    base_url: str
    model: str
    timeout_seconds: int = 300
    logger: AIRequestLogger | None = None

    def chat_json(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the assistant content.

        Example:
            content = client.chat_json("Return JSON")
        """
        started_at = time.monotonic()
        try:
            response = post_json(
                self.chat_url(), self.request_payload(prompt), self.timeout_seconds
            )
            content = response_message_content(response)
        except (ConnectionError, ValueError) as error:
            self.log_request(prompt, "", started_at, "error", str(error), {})
            raise
        metrics = safe_metric_dict(response, OLLAMA_METRIC_KEYS)
        self.log_request(prompt, content, started_at, "ok", "", metrics)
        return content

    def log_request(
        self,
        prompt: str,
        content: str,
        started_at: float,
        status: str,
        error: str,
        metrics: dict[str, str | int | float | bool | None],
    ) -> None:
        """Record safe Ollama request metadata when a logger is configured.

        Example:
            client.log_request("prompt", "{}", started_at, "ok", "", {})
        """
        if self.logger is None:
            return
        entry = AIRequestLog(
            "ollama",
            self.model,
            self.base_url,
            len(prompt),
            len(content),
            time.monotonic() - started_at,
            status,
            error,
            metrics,
        )
        self.logger.record(entry)

    def chat_url(self) -> str:
        """Return the Ollama chat endpoint URL.

        Example:
            url = client.chat_url()
        """
        return f"{self.base_url.rstrip('/')}/api/chat"

    def request_payload(self, prompt: str) -> dict[str, object]:
        """Return the Ollama JSON request payload.

        Example:
            payload = client.request_payload("Hello")
        """
        return {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
        }


def post_json(
    url: str, payload: dict[str, object], timeout_seconds: int
) -> dict[str, object]:
    """Post JSON and return a decoded JSON object.

    Example:
        response = post_json("http://localhost", {}, 10)
    """
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = load_response_json(response.read(), "Ollama response", url)
    except TimeoutError as error:
        message = (
            f"Ollama timed out after {timeout_seconds}s while evaluating a project."
        )
        raise ConnectionError(message) from error
    except HTTPError as error:
        raise ConnectionError(ollama_http_error_message(error)) from error
    except URLError as error:
        message = (
            f"Could not reach Ollama at {url}: {error.reason!r}. "
            "Expected a running Ollama server."
        )
        raise ConnectionError(message) from error
    return object_json(decoded, "Ollama response")


def ollama_http_error_message(error: HTTPError) -> str:
    """Return an actionable Ollama HTTP error message.

    Example:
        message = ollama_http_error_message(error)
    """
    body = read_http_error_body(error)
    detail = ollama_error_detail(body)
    if not detail:
        detail = (
            f"Response body: {trim_error_body(body)}" if body else "No response body."
        )
    return (
        f"Ollama request failed with HTTP {error.code} "
        f"{http_error_reason(error)}: {detail}"
    )


def ollama_error_detail(body: str) -> str:
    """Return Ollama's structured error detail when present.

    Example:
        detail = ollama_error_detail('{"error": "model not found"}')
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    return error if isinstance(error, str) else ""


def response_message_content(response: dict[str, object]) -> str:
    """Extract assistant message content from an Ollama response.

    Example:
        content = response_message_content({"message": {"content": "{}"}})
    """
    message = response.get("message")
    if not isinstance(message, dict):
        raise ValueError(
            "Invalid Ollama response message; expected object at 'message'."
        )
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError(
            "Invalid Ollama response content; expected string at 'message.content'."
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
