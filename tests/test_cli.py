from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openfreela import cli
from openfreela.freelas99_scraper import FreelanceProject

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def test_main_runs_login_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []
    session_path = tmp_path / "session.json"
    monkeypatch.setattr(cli, "save_manual_login_session", calls.append)

    cli.main(["login-99freelas", "--session", str(session_path)])

    assert calls == [session_path]


def test_main_runs_scrape_command_and_saves_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "projects.json"
    session_path = tmp_path / "session.json"
    project = FreelanceProject(
        "Title", "Desc", None, ("Python",), "url", None, None, None, None, None, "raw"
    )

    def scrape_projects(path: Path, *, headless: bool = True) -> list[FreelanceProject]:
        assert path == session_path
        assert headless
        return [project]

    monkeypatch.setattr(cli, "scrape_first_projects_page", scrape_projects)

    cli.main(
        [
            "scrape-99freelas",
            "--session",
            str(session_path),
            "--output",
            str(output_path),
            "--headless",
        ]
    )

    assert json.loads(output_path.read_text()) == [project.to_dict()]


def test_main_exits_with_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_login(path: Path) -> None:
        raise FileNotFoundError(f"missing {path}")

    monkeypatch.setattr(cli, "save_manual_login_session", fail_login)

    with pytest.raises(SystemExit, match="missing"):
        cli.main(["login-99freelas", "--session", "missing.json"])


def test_build_parser_requires_known_command() -> None:
    parser = cli.build_parser()
    argv: Sequence[str] = ["unknown"]

    with pytest.raises(SystemExit):
        parser.parse_args(argv)
