from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openfreela import cli
from openfreela.browser.session import LOGIN_URL as FREELAS99_LOGIN_URL
from openfreela.evaluation.evaluator import (
    DEFAULT_CV_PATH,
    DEFAULT_EVALUATIONS_PATH,
    DEFAULT_NOTIFIED_PROJECTS_PATH,
    DEFAULT_PROMPT_PATH,
    ProjectEvaluation,
)
from openfreela.projects.model import FreelanceProject
from openfreela.sources.workana.scraper import LOGIN_URL as WORKANA_LOGIN_URL

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def test_main_runs_login_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, str]] = []
    session_path = tmp_path / "session.json"
    monkeypatch.setattr(
        cli,
        "save_manual_login_session",
        lambda path, url: calls.append((path, url)),
    )

    cli.main(["login-99freelas", "--session", str(session_path)])

    assert calls == [(session_path, FREELAS99_LOGIN_URL)]


def test_main_runs_workana_login_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, str]] = []
    session_path = tmp_path / "workana.json"
    monkeypatch.setattr(
        cli,
        "save_manual_login_session",
        lambda path, url: calls.append((path, url)),
    )

    cli.main(["login-workana", "--session", str(session_path)])

    assert calls == [(session_path, WORKANA_LOGIN_URL)]


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

    monkeypatch.setattr(cli, "scrape_99freelas_pages", scrape_projects)

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


def test_main_runs_workana_scrape_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "workana-projects.json"
    session_path = tmp_path / "workana.json"
    project = FreelanceProject(
        "Title", "Desc", None, (), "url", None, None, None, None, None, "raw", "workana"
    )

    def scrape_projects(path: Path, *, headless: bool = True) -> list[FreelanceProject]:
        assert path == session_path
        assert headless
        return [project]

    monkeypatch.setattr(cli, "scrape_workana_pages", scrape_projects)

    cli.main(
        [
            "scrape-workana",
            "--session",
            str(session_path),
            "--output",
            str(output_path),
            "--headless",
        ]
    )

    assert json.loads(output_path.read_text()) == [project.to_dict()]


def test_main_exits_with_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_login(path: Path, login_url: str) -> None:
        del login_url
        raise FileNotFoundError(f"missing {path}")

    monkeypatch.setattr(cli, "save_manual_login_session", fail_login)

    with pytest.raises(SystemExit, match="missing"):
        cli.main(["login-99freelas", "--session", "missing.json"])


def test_main_runs_evaluate_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[cli.EvaluateOptions] = []

    def run_evaluate(options: cli.EvaluateOptions) -> None:
        calls.append(options)

    monkeypatch.setattr(cli, "run_evaluate", run_evaluate)

    cli.main(
        [
            "evaluate-projects",
            "--projects",
            str(tmp_path / "projects.json"),
            "--cv",
            str(tmp_path / "cv.md"),
            "--prompt",
            str(tmp_path / "prompt.md"),
            "--output",
            str(tmp_path / "evaluations.json"),
            "--notified",
            str(tmp_path / "notified.json"),
            "--max-proposals",
            "30",
            "--ai-provider",
            "openai",
            "--ai-model",
            "gpt-4o-mini",
            "--ai-verbose",
            "--ai-log",
            str(tmp_path / "ai.jsonl"),
        ]
    )

    assert calls[0].max_proposals == 30
    assert calls[0].cv_path == tmp_path / "cv.md"
    assert calls[0].ai_provider == "openai"
    assert calls[0].ai_model == "gpt-4o-mini"
    assert calls[0].ai_verbose
    assert calls[0].ai_log_path == tmp_path / "ai.jsonl"


def test_run_evaluate_calls_project_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    evaluation = ProjectEvaluation(
        "url", "Title", 75, 70, "apply", "", "", (), (), (), (), ""
    )
    calls: list[object] = []

    monkeypatch.setattr(cli, "ai_client_from_options", lambda options: object())
    monkeypatch.setattr(cli, "telegram_from_env", lambda: object())

    def evaluate_projects(
        config: object, judge: object, notifier: object
    ) -> list[ProjectEvaluation]:
        calls.extend([config, judge, notifier])
        return [evaluation]

    monkeypatch.setattr(
        cli,
        "evaluate_project_file",
        evaluate_projects,
    )

    cli.run_evaluate(
        cli.EvaluateOptions(
            cli.DEFAULT_PROJECTS_OUTPUT_PATH,
            DEFAULT_CV_PATH,
            DEFAULT_PROMPT_PATH,
            DEFAULT_EVALUATIONS_PATH,
            DEFAULT_NOTIFIED_PROJECTS_PATH,
            30,
            "ollama",
            "qwen3.5:latest",
            False,
            None,
        )
    )

    assert len(calls) == 3


def test_required_env_rejects_missing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        cli.required_env("TELEGRAM_BOT_TOKEN")


def test_parser_requires_ai_model_for_ai_commands() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["test-ai"])

    with pytest.raises(SystemExit):
        parser.parse_args(["evaluate-projects"])


def test_run_test_ai_validates_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeJudge:
        def chat_json(self, prompt: str) -> str:
            return '{"ok": true}'

    monkeypatch.setattr(cli, "ai_client_from_options", lambda options: FakeJudge())

    cli.run_test_ai(cli.TestAIOptions("ollama", "qwen3.5:latest", False, None))


def test_run_test_ai_rejects_bad_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJudge:
        def chat_json(self, prompt: str) -> str:
            return '{"ok": false}'

    monkeypatch.setattr(cli, "ai_client_from_options", lambda options: FakeJudge())

    with pytest.raises(ValueError, match="expected ok=true"):
        cli.run_test_ai(cli.TestAIOptions("ollama", "qwen3.5:latest", False, None))


def test_build_parser_requires_known_command() -> None:
    parser = cli.build_parser()
    argv: Sequence[str] = ["unknown"]

    with pytest.raises(SystemExit):
        parser.parse_args(argv)
