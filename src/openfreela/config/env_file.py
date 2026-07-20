from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load KEY=value pairs from a .env file without overriding real env vars.

    Example:
        load_dotenv(Path(".env"))
    """
    if not path.exists():
        return
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        load_dotenv_line(line, line_number, path)


def load_dotenv_line(line: str, line_number: int, path: Path) -> None:
    """Load one .env line into os.environ if valid.

    Example:
        load_dotenv_line("KEY=value", 1, Path(".env"))
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    if "=" not in stripped:
        raise ValueError(
            f"Invalid .env line {line_number} in {path}; expected KEY=value."
        )
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError(
            f"Invalid .env line {line_number} in {path}; expected non-empty KEY."
        )
    os.environ.setdefault(key, clean_env_value(value))


def clean_env_value(value: str) -> str:
    """Return a normalized .env value, removing simple wrapping quotes.

    Example:
        value = clean_env_value('"hello"')
    """
    cleaned = value.strip()
    if len(cleaned) < 2:
        return cleaned
    if cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned
