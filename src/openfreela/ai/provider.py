from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openfreela.ai.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    OllamaClient,
)
from openfreela.ai.openai_client import (
    DEFAULT_OPENAI_BASE_URL,
    OpenAIClient,
)
from openfreela.ai.request_logger import SafeAIRequestLogger

if TYPE_CHECKING:
    from pathlib import Path

    from openfreela.evaluation.evaluator import ProjectJudge

DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_AI_TIMEOUT_SECONDS = 300
AI_PROVIDERS = ("ollama", "openai")


@dataclass(frozen=True)
class AIProviderOptions:
    """Options used to construct an AI project judge.

    Example:
        options = AIProviderOptions("ollama", "qwen3.5:latest")
    """

    provider: str
    model: str
    verbose: bool = False
    log_path: Path | None = None


def ai_client_from_options(options: AIProviderOptions) -> ProjectJudge:
    """Create an AI client for the selected provider.

    Example:
        judge = ai_client_from_options(AIProviderOptions("ollama", "qwen3.5:latest"))
    """
    provider = validate_ai_provider(options.provider)
    logger = SafeAIRequestLogger(options.verbose, options.log_path)
    if provider == "ollama":
        return ollama_client_from_env(options.model, logger, options.verbose)
    return openai_client_from_env(options.model, logger, options.verbose)


def ollama_client_from_env(
    model: str, logger: SafeAIRequestLogger, verbose: bool
) -> OllamaClient:
    """Create an Ollama client from environment variables.

    Example:
        client = ollama_client_from_env("qwen3.5:latest", logger, False)
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    if verbose:
        print("AI provider: ollama")
        print(f"AI model: {model}")
        print(f"AI base URL: {base_url}")
    return OllamaClient(base_url, model, DEFAULT_AI_TIMEOUT_SECONDS, logger)


def openai_client_from_env(
    model: str, logger: SafeAIRequestLogger, verbose: bool
) -> OpenAIClient:
    """Create an OpenAI client from environment variables.

    Example:
        client = openai_client_from_env("gpt-4o-mini", logger, False)
    """
    base_url = DEFAULT_OPENAI_BASE_URL
    api_key = required_env("OPENAI_API_KEY")
    if verbose:
        print("AI provider: openai")
        print(f"AI model: {model}")
        print(f"AI base URL: {base_url}")
    return OpenAIClient(base_url, model, api_key, DEFAULT_AI_TIMEOUT_SECONDS, logger)


def validate_ai_provider(value: str | None) -> str:
    """Return a supported AI provider name.

    Example:
        provider = validate_ai_provider("ollama")
    """
    provider = value or DEFAULT_AI_PROVIDER
    if provider in AI_PROVIDERS:
        return provider
    expected = ", ".join(AI_PROVIDERS)
    raise ValueError(f"Invalid AI provider {provider!r}; expected one of: {expected}.")


def required_env(name: str) -> str:
    """Return a required non-empty environment variable.

    Example:
        token = required_env("OPENAI_API_KEY")
    """
    value = os.environ.get(name)
    if value:
        return value
    raise RuntimeError(
        f"Missing environment variable {name}; expected a non-empty value."
    )
