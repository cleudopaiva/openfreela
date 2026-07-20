from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from openfreela.ai.provider import (
    AI_PROVIDERS,
    DEFAULT_AI_PROVIDER,
    AIProviderOptions,
    ai_client_from_options,
)
from openfreela.browser.session import (
    DEFAULT_SESSION_PATH,
    save_manual_login_session,
)
from openfreela.browser.session import (
    LOGIN_URL as FREELAS99_LOGIN_URL,
)
from openfreela.config.env_file import load_dotenv
from openfreela.evaluation.evaluator import (
    DEFAULT_CV_PATH,
    DEFAULT_EVALUATIONS_PATH,
    DEFAULT_NOTIFIED_PROJECTS_PATH,
    DEFAULT_PROMPT_PATH,
    EvaluationRunConfig,
    evaluate_project_file,
    load_json_object,
)
from openfreela.notifications.telegram import TelegramNotifier
from openfreela.sources.freelas99.scraper import SessionExpiredError
from openfreela.sources.freelas99.scraper import (
    scrape_projects_pages as scrape_99freelas_pages,
)
from openfreela.sources.workana.scraper import LOGIN_URL as WORKANA_LOGIN_URL
from openfreela.sources.workana.scraper import (
    scrape_projects_pages as scrape_workana_pages,
)

DEFAULT_PROJECTS_OUTPUT_PATH = Path("data/99freelas-projects.json")
DEFAULT_WORKANA_SESSION_PATH = Path(".auth/workana.json")
DEFAULT_WORKANA_OUTPUT_PATH = Path("data/workana-projects.json")

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openfreela.projects.model import FreelanceProject


@dataclass(frozen=True)
class LoginOptions:
    """Options for saving a manual login session.

    Example:
        options = LoginOptions(
            Path(".auth/99freelas.json"), "https://example.com", "example"
        )
    """

    session_path: Path
    login_url: str
    source_name: str


class ProjectScraper(Protocol):
    """Callable project scraper used by source-specific CLI commands."""

    def __call__(
        self, session_path: Path, *, headless: bool = True
    ) -> list[FreelanceProject]:
        """Scrape projects from one freelance source."""


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
            Path("out.json"), Path("notified.json"), 30, "ollama",
            "qwen3.5:latest", False, None
        )
    """

    projects_path: Path
    cv_path: Path
    prompt_path: Path
    output_path: Path
    notified_path: Path
    max_proposals: int | None
    ai_provider: str
    ai_model: str
    ai_verbose: bool
    ai_log_path: Path | None


@dataclass(frozen=True)
class TestAIOptions:
    """Options for checking the configured AI provider.

    Example:
        options = TestAIOptions("ollama", "qwen3.5:latest", True, None)
    """

    ai_provider: str
    ai_model: str
    ai_verbose: bool
    ai_log_path: Path | None


def main(argv: Sequence[str] | None = None) -> None:
    """Run the openfreela command line interface.

    Example:
        main(["scrape-99freelas"])
    """
    load_dotenv()
    try:
        parser = build_parser()
        namespace = parser.parse_args(argv)
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
    add_workana_login_parser(subparsers)
    add_scrape_parser(subparsers)
    add_workana_scrape_parser(subparsers)
    add_evaluate_parser(subparsers)
    add_test_ai_parser(subparsers)
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


def add_workana_login_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the manual Workana login command."""
    parser = subparsers.add_parser("login-workana")
    parser.add_argument("--session", default=str(DEFAULT_WORKANA_SESSION_PATH))


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


def add_workana_scrape_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the Workana project scraper command."""
    parser = subparsers.add_parser("scrape-workana")
    parser.add_argument("--session", default=str(DEFAULT_WORKANA_SESSION_PATH))
    parser.add_argument("--output", default=str(DEFAULT_WORKANA_OUTPUT_PATH))
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
    parser.add_argument("--max-proposals", type=int)
    add_ai_arguments(parser)


def add_test_ai_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the AI provider healthcheck command.

    Example:
        add_test_ai_parser(parser.add_subparsers())
    """
    parser = subparsers.add_parser("test-ai")
    add_ai_arguments(parser)


def add_ai_arguments(parser: argparse.ArgumentParser) -> None:
    """Register shared AI provider arguments.

    Example:
        add_ai_arguments(parser)
    """
    parser.add_argument(
        "--ai-provider", choices=AI_PROVIDERS, default=DEFAULT_AI_PROVIDER
    )
    parser.add_argument("--ai-model", required=True)
    parser.add_argument("--ai-verbose", action="store_true")
    parser.add_argument("--ai-log")


def run_command(namespace: argparse.Namespace) -> None:
    """Dispatch parsed CLI options to the requested command.

    Example:
        run_command(parser.parse_args(["scrape-99freelas"]))
    """
    command = str(namespace.command)
    if command == "login-99freelas":
        run_login(login_options(namespace, FREELAS99_LOGIN_URL, "99freelas"))
        return
    if command == "login-workana":
        run_login(login_options(namespace, WORKANA_LOGIN_URL, "Workana"))
        return
    if command == "scrape-99freelas":
        run_scrape(scrape_options(namespace), scrape_99freelas_pages)
        return
    if command == "scrape-workana":
        run_scrape(scrape_options(namespace), scrape_workana_pages)
        return
    if command == "evaluate-projects":
        run_evaluate(evaluate_options(namespace))
        return
    if command == "test-ai":
        run_test_ai(test_ai_options(namespace))


def login_options(
    namespace: argparse.Namespace, login_url: str, source_name: str
) -> LoginOptions:
    """Convert parsed login arguments into typed options.

    Example:
        options = login_options(parser.parse_args(["login-99freelas"]))
    """
    return LoginOptions(
        session_path=Path(str(namespace.session)),
        login_url=login_url,
        source_name=source_name,
    )


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
        max_proposals=optional_non_negative_int(
            namespace.max_proposals, "--max-proposals"
        ),
        ai_provider=str(namespace.ai_provider),
        ai_model=str(namespace.ai_model),
        ai_verbose=bool(namespace.ai_verbose),
        ai_log_path=optional_path(namespace.ai_log),
    )


def test_ai_options(namespace: argparse.Namespace) -> TestAIOptions:
    """Convert parsed AI test arguments into typed options.

    Example:
        options = test_ai_options(parser.parse_args(["test-ai"]))
    """
    return TestAIOptions(
        ai_provider=str(namespace.ai_provider),
        ai_model=str(namespace.ai_model),
        ai_verbose=bool(namespace.ai_verbose),
        ai_log_path=optional_path(namespace.ai_log),
    )


def run_login(options: LoginOptions) -> None:
    """Open a browser for manual login and save the session file.

    Example:
        run_login(LoginOptions(Path(".auth/99freelas.json")))
    """
    save_manual_login_session(options.session_path, options.login_url)
    print(f"Saved {options.source_name} session to {options.session_path}")


def run_scrape(
    options: ScrapeOptions,
    scrape_projects: ProjectScraper,
) -> None:
    """Scrape projects and write the local JSON output file.

    Example:
        run_scrape(
            ScrapeOptions(Path(".auth/session.json"), Path("data/out.json"), True)
        )
    """
    projects = scrape_projects(options.session_path, headless=options.headless)
    save_projects(options.output_path, projects)
    print(f"Saved {len(projects)} projects to {options.output_path}")


def run_evaluate(options: EvaluateOptions) -> None:
    """Evaluate projects with Ollama and notify strong apply matches.

    Example:
        run_evaluate(options)
    """
    config = evaluation_config(options)
    judge = ai_client_from_options(ai_provider_options(options))
    evaluations = evaluate_project_file(config, judge, telegram_from_env())
    print(f"Saved {len(evaluations)} evaluations to {options.output_path}")


def run_test_ai(options: TestAIOptions) -> None:
    """Send a tiny JSON prompt to the configured AI provider.

    Example:
        run_test_ai(TestAIOptions("ollama", "qwen3.5:latest", False, None))
    """
    judge = ai_client_from_options(
        AIProviderOptions(
            options.ai_provider,
            options.ai_model,
            options.ai_verbose,
            options.ai_log_path,
        )
    )
    content = judge.chat_json('Return exactly this JSON object: {"ok": true}')
    payload = load_json_object(content)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError(f"Invalid AI test response {payload!r}; expected ok=true.")
    print(f"AI provider test passed: {options.ai_provider}")


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
        options.max_proposals,
    )


def ai_provider_options(options: EvaluateOptions) -> AIProviderOptions:
    """Return AI provider options from evaluation options.

    Example:
        ai_options = ai_provider_options(options)
    """
    return AIProviderOptions(
        options.ai_provider,
        options.ai_model,
        options.ai_verbose,
        options.ai_log_path,
    )


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


def optional_path(value: object) -> Path | None:
    """Return a Path for a provided CLI value, otherwise None.

    Example:
        path = optional_path("data/ai.jsonl")
    """
    if value is None:
        return None
    return Path(str(value))


def optional_non_negative_int(value: object, label: str) -> int | None:
    """Return an optional non-negative integer value.

    Example:
        limit = optional_non_negative_int(30, "--max-proposals")
    """
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"Invalid {label}={value!r}; expected integer.")
    parsed = value
    if parsed >= 0:
        return parsed
    raise ValueError(f"Invalid {label}={parsed}; expected non-negative integer.")


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
