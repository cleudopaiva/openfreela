from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from openfreela.browser_session import DEFAULT_SESSION_PATH, save_manual_login_session
from openfreela.freelas99_scraper import (
    FreelanceProject,
    SessionExpiredError,
    scrape_projects_pages,
)
from openfreela.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaClient,
)
from openfreela.project_evaluator import (
    DEFAULT_CV_PATH,
    DEFAULT_EVALUATIONS_PATH,
    DEFAULT_MIN_PROFILE_MATCH,
    DEFAULT_NOTIFIED_PROJECTS_PATH,
    DEFAULT_PROMPT_PATH,
    EvaluationRunConfig,
    evaluate_project_file,
)
from openfreela.telegram_notifier import TelegramNotifier

DEFAULT_PROJECTS_OUTPUT_PATH = Path("data/99freelas-projects.json")

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class LoginOptions:
    """Options for saving a manual login session.

    Example:
        options = LoginOptions(Path(".auth/99freelas.json"))
    """

    session_path: Path


@dataclass(frozen=True)
class ScrapeOptions:
    """Options for scraping the first projects page.

    Example:
        options = ScrapeOptions(
            Path(".auth/99freelas.json"), Path("data/out.json"), True
        )
    """

    session_path: Path
    output_path: Path
    headless: bool


@dataclass(frozen=True)
class EvaluateOptions:
    """Options for evaluating scraped projects with AI.

    Example:
        options = EvaluateOptions(
            Path("projects.json"), Path("cv.md"), Path("prompt.md"),
            Path("out.json"), Path("notified.json"), 75
        )
    """

    projects_path: Path
    cv_path: Path
    prompt_path: Path
    output_path: Path
    notified_path: Path
    min_profile_match: int


def main(argv: Sequence[str] | None = None) -> None:
    """Run the openfreela command line interface.

    Example:
        main(["scrape-99freelas"])
    """
    parser = build_parser()
    namespace = parser.parse_args(argv)
    try:
        run_command(namespace)
    except (
        ConnectionError,
        FileNotFoundError,
        RuntimeError,
        SessionExpiredError,
        ValueError,
    ) as error:
        raise SystemExit(str(error)) from error


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI parser.

    Example:
        parser = build_parser()
    """
    parser = argparse.ArgumentParser(prog="openfreela")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_login_parser(subparsers)
    add_scrape_parser(subparsers)
    add_evaluate_parser(subparsers)
    return parser


def add_login_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the manual 99freelas login command.

    Example:
        add_login_parser(parser.add_subparsers())
    """
    parser = subparsers.add_parser("login-99freelas")
    parser.add_argument("--session", default=str(DEFAULT_SESSION_PATH))


def add_scrape_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the first-page 99freelas scraper command.

    Example:
        add_scrape_parser(parser.add_subparsers())
    """
    parser = subparsers.add_parser("scrape-99freelas")
    parser.add_argument("--session", default=str(DEFAULT_SESSION_PATH))
    parser.add_argument("--output", default=str(DEFAULT_PROJECTS_OUTPUT_PATH))
    parser.add_argument("--headless", action="store_true")


def add_evaluate_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the AI project evaluation command.

    Example:
        add_evaluate_parser(parser.add_subparsers())
    """
    parser = subparsers.add_parser("evaluate-projects")
    parser.add_argument("--projects", default=str(DEFAULT_PROJECTS_OUTPUT_PATH))
    parser.add_argument("--cv", default=str(DEFAULT_CV_PATH))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH))
    parser.add_argument("--output", default=str(DEFAULT_EVALUATIONS_PATH))
    parser.add_argument("--notified", default=str(DEFAULT_NOTIFIED_PROJECTS_PATH))
    parser.add_argument("--min-score", type=int, default=env_min_profile_match())


def run_command(namespace: argparse.Namespace) -> None:
    """Dispatch parsed CLI options to the requested command.

    Example:
        run_command(parser.parse_args(["scrape-99freelas"]))
    """
    command = str(namespace.command)
    if command == "login-99freelas":
        run_login(login_options(namespace))
        return
    if command == "scrape-99freelas":
        run_scrape(scrape_options(namespace))
        return
    if command == "evaluate-projects":
        run_evaluate(evaluate_options(namespace))


def login_options(namespace: argparse.Namespace) -> LoginOptions:
    """Convert parsed login arguments into typed options.

    Example:
        options = login_options(parser.parse_args(["login-99freelas"]))
    """
    return LoginOptions(session_path=Path(str(namespace.session)))


def scrape_options(namespace: argparse.Namespace) -> ScrapeOptions:
    """Convert parsed scrape arguments into typed options.

    Example:
        options = scrape_options(parser.parse_args(["scrape-99freelas"]))
    """
    return ScrapeOptions(
        session_path=Path(str(namespace.session)),
        output_path=Path(str(namespace.output)),
        headless=bool(namespace.headless),
    )


def evaluate_options(namespace: argparse.Namespace) -> EvaluateOptions:
    """Convert parsed evaluation arguments into typed options.

    Example:
        options = evaluate_options(parser.parse_args(["evaluate-projects"]))
    """
    return EvaluateOptions(
        projects_path=Path(str(namespace.projects)),
        cv_path=Path(str(namespace.cv)),
        prompt_path=Path(str(namespace.prompt)),
        output_path=Path(str(namespace.output)),
        notified_path=Path(str(namespace.notified)),
        min_profile_match=int(namespace.min_score),
    )


def run_login(options: LoginOptions) -> None:
    """Open a browser for manual login and save the session file.

    Example:
        run_login(LoginOptions(Path(".auth/99freelas.json")))
    """
    save_manual_login_session(options.session_path)
    print(f"Saved 99freelas session to {options.session_path}")


def run_scrape(options: ScrapeOptions) -> None:
    """Scrape projects and write the local JSON output file.

    Example:
        run_scrape(
            ScrapeOptions(Path(".auth/session.json"), Path("data/out.json"), True)
        )
    """
    projects = scrape_projects_pages(options.session_path, headless=options.headless)
    save_projects(options.output_path, projects)
    print(f"Saved {len(projects)} projects to {options.output_path}")


def run_evaluate(options: EvaluateOptions) -> None:
    """Evaluate projects with Ollama and notify strong apply matches.

    Example:
        run_evaluate(options)
    """
    config = evaluation_config(options)
    evaluations = evaluate_project_file(
        config, ollama_client_from_env(), telegram_from_env()
    )
    print(f"Saved {len(evaluations)} evaluations to {options.output_path}")


def evaluation_config(options: EvaluateOptions) -> EvaluationRunConfig:
    """Return evaluator run configuration from CLI options.

    Example:
        config = evaluation_config(options)
    """
    return EvaluationRunConfig(
        options.projects_path,
        options.cv_path,
        options.prompt_path,
        options.output_path,
        options.notified_path,
        options.min_profile_match,
    )


def ollama_client_from_env() -> OllamaClient:
    """Create an Ollama client from environment variables.

    Example:
        client = ollama_client_from_env()
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    return OllamaClient(base_url, model)


def telegram_from_env() -> TelegramNotifier:
    """Create a Telegram notifier from required environment variables.

    Example:
        notifier = telegram_from_env()
    """
    token = required_env("TELEGRAM_BOT_TOKEN")
    chat_id = required_env("TELEGRAM_CHAT_ID")
    return TelegramNotifier(token, chat_id)


def required_env(name: str) -> str:
    """Return a required non-empty environment variable.

    Example:
        token = required_env("TELEGRAM_BOT_TOKEN")
    """
    value = os.environ.get(name)
    if value:
        return value
    raise RuntimeError(
        f"Missing environment variable {name}; expected a non-empty value."
    )


def env_min_profile_match() -> int:
    """Return the default profile match threshold from the environment.

    Example:
        score = env_min_profile_match()
    """
    value = os.environ.get("OPENFREELA_MIN_PROFILE_MATCH")
    if value is None:
        return DEFAULT_MIN_PROFILE_MATCH
    return int(value)


def save_projects(output_path: Path, projects: list[FreelanceProject]) -> None:
    """Save projects as pretty JSON for later AI-based filtering.

    Example:
        save_projects(Path("data/projects.json"), projects)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [project.to_dict() for project in projects]
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
