from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from openfreela.projects.model import FreelanceProject
from openfreela.sources.workana import scraper as workana_scraper
from openfreela.sources.workana.html import ParsedWorkanaProject
from openfreela.sources.workana.scraper import (
    absolute_project_url,
    browser_context_with_session,
    collect_projects,
    dedupe_projects,
    ensure_session_exists,
    pagination_page_urls,
    project_from_parsed_item,
    project_page_url,
    scrape_context_project_pages,
    wait_for_project_cards,
)

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Browser, BrowserContext, Locator, Page


class FakeBrowser:
    """Fake Playwright browser with context fallback behavior.

    Example:
        browser = FakeBrowser(fail_new_context=False)
    """

    def __init__(self, *, fail_new_context: bool) -> None:
        self.contexts = [object()]
        self.fail_new_context = fail_new_context

    def new_context(self, *, storage_state: str) -> object:
        """Return a context or simulate a Playwright CDP context failure."""
        if self.fail_new_context:
            raise PlaywrightError("cannot create context")
        return {"storage_state": storage_state}


class FakeFirstLocator:
    """Fake first locator used by wait tests.

    Example:
        locator = FakeFirstLocator(raises_timeout=False)
    """

    def __init__(self, *, raises_timeout: bool) -> None:
        self.raises_timeout = raises_timeout
        self.wait_calls: list[tuple[str, int]] = []

    def wait_for(self, *, state: str, timeout: int) -> None:
        """Record waits or raise a Playwright timeout."""
        self.wait_calls.append((state, timeout))
        if self.raises_timeout:
            raise PlaywrightTimeoutError("timed out")


class FakeWaitLocator:
    """Fake locator that exposes a first locator.

    Example:
        locator = FakeWaitLocator(FakeFirstLocator(raises_timeout=False))
    """

    def __init__(self, first: FakeFirstLocator) -> None:
        self.first = first


class FakeHrefLocator:
    """Fake locator for pagination href extraction.

    Example:
        locator = FakeHrefLocator(["/jobs?page=2"])
    """

    def __init__(self, hrefs: list[str]) -> None:
        self.hrefs = hrefs

    def count(self) -> int:
        """Return link count."""
        return len(self.hrefs)

    def nth(self, index: int) -> FakeHrefLocator:
        """Return one fake href locator."""
        return FakeHrefLocator([self.hrefs[index]])

    def get_attribute(self, name: str) -> str | None:
        """Return href when requested."""
        assert name == "href"
        return self.hrefs[0] if self.hrefs else None


class FakePagingPage:
    """Fake page with pagination links.

    Example:
        page = FakePagingPage(["/jobs?page=2"])
    """

    def __init__(self, hrefs: list[str]) -> None:
        self.hrefs = hrefs

    def locator(self, selector: str) -> FakeHrefLocator:
        """Return fake pagination links."""
        assert selector == workana_scraper.PAGINATION_LINK_SELECTOR
        return FakeHrefLocator(self.hrefs)


class FakePagingContext:
    """Fake browser context for all-pages orchestration tests.

    Example:
        context = FakePagingContext()
    """

    def __init__(self) -> None:
        self.page = object()

    def new_page(self) -> object:
        """Return a stable fake page object."""
        return self.page


def test_project_page_url_uses_workana_category() -> None:
    assert project_page_url(1) == workana_scraper.PROJECTS_URL
    assert project_page_url(2).endswith("category=it-programming&page=2")


def test_project_page_url_rejects_invalid_page() -> None:
    with pytest.raises(ValueError, match="expected page >= 1"):
        project_page_url(0)


def test_pagination_page_urls_reads_workana_links() -> None:
    page = cast(
        "Page",
        FakePagingPage([
            "https://www.workana.com/jobs?category=it-programming&page=2",
            "https://www.workana.com/jobs?category=it-programming&page=3",
        ]),
    )

    assert pagination_page_urls(page) == [
        workana_scraper.PROJECTS_URL,
        "https://www.workana.com/jobs?category=it-programming&page=2",
        "https://www.workana.com/jobs?category=it-programming&page=3",
    ]


def test_project_from_parsed_item_normalizes_workana_fields() -> None:
    item = ParsedWorkanaProject(
        "Title", "Desc", "USD 50 - 100", ("Python",), "/job/x", "hoje", 3, "raw"
    )

    project = project_from_parsed_item(item)

    assert project.source == "workana"
    assert project.project_url == "https://www.workana.com/job/x"
    assert project.proposals == 3
    assert project.budget == "USD 50 - 100"


def test_absolute_project_url_rejects_empty_href() -> None:
    assert absolute_project_url(" ") is None


def test_browser_context_with_session_uses_new_context(tmp_path: Path) -> None:
    browser = cast("Browser", FakeBrowser(fail_new_context=False))

    context = browser_context_with_session(browser, tmp_path / "workana.json")

    assert cast("object", context) == {"storage_state": str(tmp_path / "workana.json")}


def test_browser_context_with_session_falls_back_to_default(tmp_path: Path) -> None:
    fake_browser = FakeBrowser(fail_new_context=True)
    browser = cast("Browser", fake_browser)

    assert (
        browser_context_with_session(browser, tmp_path / "workana.json")
        is fake_browser.contexts[0]
    )


def test_ensure_session_exists_fails_with_actionable_message(tmp_path: Path) -> None:
    session_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="run login-workana first"):
        ensure_session_exists(session_path)


def test_wait_for_project_cards_reports_missing_cards() -> None:
    locator = cast("Locator", FakeWaitLocator(FakeFirstLocator(raises_timeout=True)))

    with pytest.raises(RuntimeError, match="No Workana project cards found"):
        wait_for_project_cards(locator)


def test_collect_projects_deduplicates_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    projects = [
        FreelanceProject("A", "", None, (), "url-a", None, None, None, None, None, ""),
        FreelanceProject("B", "", None, (), "url-a", None, None, None, None, None, ""),
    ]

    assert [project.title for project in dedupe_projects(projects)] == ["A"]
    monkeypatch.setattr(workana_scraper, "project_from_card", lambda card: projects[0])
    assert collect_projects(cast("Locator", FakeHrefLocator(["a"]))) == [projects[0]]


def test_scrape_context_project_pages_collects_all_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    first = FreelanceProject(
        "A", "", None, (), "url-a", None, None, None, None, None, ""
    )
    second = FreelanceProject(
        "B", "", None, (), "url-b", None, None, None, None, None, ""
    )

    def collect_page(page: object, page_url: str) -> list[FreelanceProject]:
        calls.append(page_url)
        return [first] if len(calls) == 1 else [second]

    monkeypatch.setattr(workana_scraper, "collect_projects_from_page", collect_page)
    monkeypatch.setattr(
        workana_scraper, "pagination_page_urls", lambda page: ["p1", "p2"]
    )

    projects = scrape_context_project_pages(cast("BrowserContext", FakePagingContext()))

    assert calls == [workana_scraper.PROJECTS_URL, "p2"]
    assert [project.project_url for project in projects] == ["url-a", "url-b"]
