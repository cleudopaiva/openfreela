from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from openfreela.browser_session import DEFAULT_SESSION_PATH, save_manual_login_session
from openfreela.freelas99_scraper import (
    FreelanceProject,
    SessionExpiredError,
    scrape_first_projects_page,
)

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


def main(argv: Sequence[str] | None = None) -> None:
    """Run the openfreela command line interface.

    Example:
        main(["scrape-99freelas"])
    """
    parser = build_parser()
    namespace = parser.parse_args(argv)
    try:
        run_command(namespace)
    except (FileNotFoundError, SessionExpiredError) as error:
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
    projects = scrape_first_projects_page(
        options.session_path, headless=options.headless
    )
    save_projects(options.output_path, projects)
    print(f"Saved {len(projects)} projects to {options.output_path}")


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
