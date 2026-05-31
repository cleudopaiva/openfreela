from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openfreela.ai_request_logger import SafeAIRequestLogger
from openfreela.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaClient,
)
from openfreela.openai_client import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    OpenAIClient,
)

if TYPE_CHECKING:
    from pathlib import Path

    from openfreela.project_evaluator import ProjectJudge

DEFAULT_AI_PROVIDER = "ollama"
AI_PROVIDERS = ("ollama", "openai")


@dataclass(frozen=True)
class AIProviderOptions:
    """Options used to construct an AI project judge.

    Example:
        options = AIProviderOptions("ollama", True, Path("data/ai.jsonl"))
    """

    provider: str
    verbose: bool = False
    log_path: Path | None = None


def ai_client_from_options(options: AIProviderOptions) -> ProjectJudge:
    """Create an AI client for the selected provider.

    Example:
        judge = ai_client_from_options(AIProviderOptions("ollama"))
    """
    provider = validate_ai_provider(options.provider)
    logger = SafeAIRequestLogger(options.verbose, options.log_path)
    if provider == "ollama":
        return ollama_client_from_env(logger, options.verbose)
    return openai_client_from_env(logger, options.verbose)


def ollama_client_from_env(logger: SafeAIRequestLogger, verbose: bool) -> OllamaClient:
    """Create an Ollama client from environment variables.

    Example:
        client = ollama_client_from_env(logger, False)
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    timeout = env_int("OPENFREELA_OLLAMA_TIMEOUT", 300)
    if verbose:
        print("AI provider: ollama")
        print(f"AI model: {model}")
        print(f"AI base URL: {base_url}")
    return OllamaClient(base_url, model, timeout, logger)


def openai_client_from_env(logger: SafeAIRequestLogger, verbose: bool) -> OpenAIClient:
    """Create an OpenAI client from environment variables.

    Example:
        client = openai_client_from_env(logger, False)
    """
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)
    model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    api_key = required_env("OPENAI_API_KEY")
    timeout = env_int("OPENFREELA_OPENAI_TIMEOUT", 300)
    if verbose:
        print("AI provider: openai")
        print(f"AI model: {model}")
        print(f"AI base URL: {base_url}")
    return OpenAIClient(base_url, model, api_key, timeout, logger)


def env_ai_provider() -> str:
    """Return the default AI provider from the environment.

    Example:
        provider = env_ai_provider()
    """
    return validate_ai_provider(os.environ.get("OPENFREELA_AI_PROVIDER"))


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


def env_int(name: str, default: int) -> int:
    """Return an integer environment variable or a default value.

    Example:
        timeout = env_int("OPENFREELA_OLLAMA_TIMEOUT", 300)
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)
