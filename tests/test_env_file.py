from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from openfreela.env_file import load_dotenv

if TYPE_CHECKING:
    from pathlib import Path


def test_load_dotenv_reads_values_without_overriding_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "# comment",
                "export OLLAMA_BASE_URL='http://localhost:11434'",
                'TELEGRAM_CHAT_ID="chat-id"',
                "OPENAI_API_KEY=from-file",
            ]
        )
    )
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    load_dotenv(path)

    assert os.environ["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert os.environ["TELEGRAM_CHAT_ID"] == "chat-id"
    assert os.environ["OPENAI_API_KEY"] == "from-shell"


def test_load_dotenv_rejects_invalid_line(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY\n")

    with pytest.raises(ValueError, match="expected KEY=value"):
        load_dotenv(path)
