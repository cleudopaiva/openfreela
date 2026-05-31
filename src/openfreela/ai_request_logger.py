from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

JsonScalar = str | int | float | bool | None


class AIRequestLogger(Protocol):
    """Protocol for safe AI request metadata logging.

    Example:
        logger.record(entry)
    """

    def record(self, entry: AIRequestLog) -> None:
        """Record one AI request without raw prompt or API token data."""


@dataclass(frozen=True)
class AIRequestLog:
    """Safe metadata about one AI request.

    Example:
        entry = AIRequestLog("ollama", "qwen", "http://localhost", 10, 2, 1.0, "ok")
    """

    provider: str
    model: str
    base_url: str
    prompt_chars: int
    response_chars: int
    duration_seconds: float
    status: str
    error: str = ""
    metrics: dict[str, JsonScalar] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable metadata object.

        Example:
            payload = entry.to_dict()
        """
        payload: dict[str, object] = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "prompt_chars": self.prompt_chars,
            "response_chars": self.response_chars,
            "duration_seconds": round(self.duration_seconds, 3),
            "status": self.status,
        }
        if self.error:
            payload["error"] = self.error
        if self.metrics:
            payload["metrics"] = self.metrics
        return payload


@dataclass(frozen=True)
class SafeAIRequestLogger:
    """Print and persist safe AI request metadata.

    Example:
        logger = SafeAIRequestLogger(True, Path("data/ai.log.jsonl"))
    """

    verbose: bool = False
    log_path: Path | None = None

    def record(self, entry: AIRequestLog) -> None:
        """Record one AI request to stdout and/or JSONL.

        Example:
            logger.record(entry)
        """
        if self.verbose:
            print(verbose_message(entry))
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")


def verbose_message(entry: AIRequestLog) -> str:
    """Return a safe human-readable AI request log line.

    Example:
        text = verbose_message(entry)
    """
    if entry.status == "ok":
        return (
            f"AI response received: provider={entry.provider} model={entry.model} "
            f"duration={entry.duration_seconds:.2f}s "
            f"prompt_chars={entry.prompt_chars} response_chars={entry.response_chars}"
        )
    return (
        f"AI request failed: provider={entry.provider} model={entry.model} "
        f"duration={entry.duration_seconds:.2f}s error={entry.error}"
    )


def safe_metric_dict(
    response: dict[str, object], keys: tuple[str, ...]
) -> dict[str, JsonScalar]:
    """Extract JSON-safe scalar metrics from an AI response object.

    Example:
        metrics = safe_metric_dict(response, ("eval_count",))
    """
    metrics: dict[str, JsonScalar] = {}
    for key in keys:
        value = response.get(key)
        if isinstance(value, str | int | float | bool) or value is None:
            metrics[key] = value
    return metrics
