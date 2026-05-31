from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urllib.error import HTTPError


def load_response_json(body: bytes, label: str, url: str) -> object:
    """Decode a provider response body as JSON with URL context.

    Example:
        payload = load_response_json(b"{}", "OpenAI response", url)
    """
    text = body.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        message = f"Invalid {label} from {url}; expected JSON object."
        raise ValueError(message) from error


def read_http_error_body(error: HTTPError) -> str:
    """Read an HTTP error body safely as text.

    Example:
        body = read_http_error_body(error)
    """
    return error.read().decode("utf-8", errors="replace")


def trim_error_body(body: str) -> str:
    """Return a bounded one-line error body snippet.

    Example:
        text = trim_error_body("error")
    """
    return " ".join(body.split())[:1000]


def http_error_reason(error: HTTPError) -> str:
    """Return the HTTP reason phrase from a urllib HTTPError.

    Example:
        reason = http_error_reason(error)
    """
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return reason
    if isinstance(error.msg, str) and error.msg:
        return error.msg
    return "Unknown"
