from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:latest"


@dataclass(frozen=True)
class OllamaClient:
    """Small HTTP client for Ollama chat completions.

    Example:
        client = OllamaClient("http://localhost:11434", "qwen3.5:latest")
    """

    base_url: str
    model: str
    timeout_seconds: int = 300

    def chat_json(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the assistant content.

        Example:
            content = client.chat_json("Return JSON")
        """
        response = post_json(
            self.chat_url(), self.request_payload(prompt), self.timeout_seconds
        )
        return response_message_content(response)

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
            decoded = json.loads(response.read().decode("utf-8"))
    except URLError as error:
        message = f"Could not reach Ollama at {url}; expected a running Ollama server."
        raise ConnectionError(message) from error
    return object_json(decoded, "Ollama response")


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
