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
                "OPENFREELA_AI_PROVIDER=ollama",
                "export OLLAMA_MODEL='qwen3.5:latest'",
                'OPENAI_MODEL="gpt-4o-mini"',
                "OPENAI_API_KEY=from-file",
            ]
        )
    )
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    monkeypatch.delenv("OPENFREELA_AI_PROVIDER", raising=False)

    load_dotenv(path)

    assert os.environ["OPENFREELA_AI_PROVIDER"] == "ollama"
    assert os.environ["OLLAMA_MODEL"] == "qwen3.5:latest"
    assert os.environ["OPENAI_MODEL"] == "gpt-4o-mini"
    assert os.environ["OPENAI_API_KEY"] == "from-shell"


def test_load_dotenv_rejects_invalid_line(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY\n")

    with pytest.raises(ValueError, match="expected KEY=value"):
        load_dotenv(path)
