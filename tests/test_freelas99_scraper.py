from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from openfreela import freelas99_scraper
from openfreela.freelas99_scraper import (
    FreelanceProject,
    SessionExpiredError,
    absolute_project_url,
    browser_context_with_session,
    build_description,
    collect_projects,
    ensure_session_exists,
    extract_skills,
    first_content_line,
    first_matching_line,
    is_login_url,
    locator_text_or_empty,
    nearest_project_text,
    parse_project_card_text,
    project_from_link,
    scrape_first_projects_page,
    split_skill_values,
    wait_for_projects_or_login,
)

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Browser, Locator


class FakeCdpDriver:
    """Fake CDP driver that records stop calls.

    Example:
        driver = FakeCdpDriver()
    """

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        """Record that the CDP browser was stopped."""
        self.stopped = True


class FakeCdpBrowser:
    """Fake SeleniumBase CDP browser for scraper orchestration tests.

    Example:
        browser = FakeCdpBrowser()
    """

    def __init__(self) -> None:
        self.driver = FakeCdpDriver()

    def get_endpoint_url(self) -> str:
        """Return a fake CDP endpoint."""
        return "http://127.0.0.1:9222"


class FakeBrowser:
    """Fake Playwright browser with context fallback behavior.

    Example:
        browser = FakeBrowser()
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


class FakeLinkLocator:
    """Fake project link locator for parser orchestration tests.

    Example:
        locator = FakeLinkLocator("/project/x", "Title")
    """

    def __init__(
        self,
        href: str | None,
        text: str,
        ancestor_texts: list[str] | None = None,
        *,
        timeout: bool = False,
    ) -> None:
        self.href = href
        self.text = text
        self.ancestor_texts = ancestor_texts or []
        self.timeout = timeout

    def get_attribute(self, name: str) -> str | None:
        """Return href when requested by the scraper."""
        return self.href if name == "href" else None

    def inner_text(self, *, timeout: int) -> str:
        """Return visible text or raise a timeout."""
        if self.timeout:
            raise PlaywrightTimeoutError("timed out")
        return self.text

    def locator(self, selector: str) -> FakeLinkLocator:
        """Return ancestor text locators in selector order."""
        del selector
        if not self.ancestor_texts:
            return FakeLinkLocator(None, "", timeout=True)
        text = self.ancestor_texts.pop(0)
        return FakeLinkLocator(None, text)


class FakeLinksLocator:
    """Fake collection of project link locators.

    Example:
        links = FakeLinksLocator([FakeLinkLocator("/project/x", "Title")])
    """

    def __init__(self, links: list[FakeLinkLocator]) -> None:
        self.links = links

    def count(self) -> int:
        """Return link count."""
        return len(self.links)

    def nth(self, index: int) -> FakeLinkLocator:
        """Return the requested fake link."""
        return self.links[index]


def test_parse_project_card_text_extracts_visible_fields() -> None:
    raw_text = """
    Criar API em Python
    Preciso de uma API com FastAPI e PostgreSQL.
    Habilidades: Python, FastAPI, PostgreSQL
    R$ 1.000 - R$ 3.000
    Publicado há 2 horas
    """

    project = parse_project_card_text(
        raw_text, "https://www.99freelas.com.br/project/api"
    )

    assert project.title == "Criar API em Python"
    assert project.budget == "R$ 1.000 - R$ 3.000"
    assert project.skills == ("Python", "FastAPI", "PostgreSQL")
    assert project.posted_at == "Publicado há 2 horas"
    assert "Preciso de uma API" in project.description


def test_freelance_project_to_dict_serializes_skills() -> None:
    project = FreelanceProject(
        "Title", "Desc", "R$ 1", ("Python",), "url", "hoje", "raw"
    )

    assert project.to_dict()["skills"] == ["Python"]


def test_absolute_project_url_keeps_99freelas_base() -> None:
    url = absolute_project_url("/project/criar-api")

    assert url == "https://www.99freelas.com.br/project/criar-api"


def test_absolute_project_url_rejects_empty_href() -> None:
    assert absolute_project_url(" ") is None


def test_is_login_url_detects_expired_session_redirect() -> None:
    assert is_login_url("https://www.99freelas.com.br/login")


def test_ensure_session_exists_fails_with_actionable_message(tmp_path: Path) -> None:
    session_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="run login-99freelas first"):
        ensure_session_exists(session_path)


def test_ensure_session_exists_accepts_existing_file(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("{}")

    ensure_session_exists(session_path)


def test_scrape_first_projects_page_stops_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.json"
    session_path.write_text("{}")
    cdp_browser = FakeCdpBrowser()
    expected = [FreelanceProject("Title", "Desc", None, (), "url", None, "raw")]
    calls: list[tuple[str, Path]] = []

    def launch_browser(*, headless: bool) -> FakeCdpBrowser:
        assert headless
        return cdp_browser

    def scrape_browser(endpoint: str, path: Path) -> list[FreelanceProject]:
        calls.append((endpoint, path))
        return expected

    monkeypatch.setattr(freelas99_scraper, "launch_cdp_browser", launch_browser)
    monkeypatch.setattr(
        freelas99_scraper,
        "scrape_connected_browser",
        scrape_browser,
    )

    projects = scrape_first_projects_page(session_path, headless=True)

    assert projects == expected
    assert calls == [("http://127.0.0.1:9222", session_path)]
    assert cdp_browser.driver.stopped


def test_browser_context_with_session_uses_new_context(tmp_path: Path) -> None:
    browser = cast("Browser", FakeBrowser(fail_new_context=False))

    context = browser_context_with_session(browser, tmp_path / "session.json")

    assert cast("object", context) == {"storage_state": str(tmp_path / "session.json")}


def test_browser_context_with_session_falls_back_to_default(tmp_path: Path) -> None:
    fake_browser = FakeBrowser(fail_new_context=True)
    browser = cast("Browser", fake_browser)

    assert (
        browser_context_with_session(browser, tmp_path / "session.json")
        is fake_browser.contexts[0]
    )


def test_wait_for_projects_or_login_rejects_login_redirect() -> None:
    locator = cast("Locator", FakeWaitLocator(FakeFirstLocator(raises_timeout=False)))

    with pytest.raises(SessionExpiredError, match="Session expired"):
        wait_for_projects_or_login("https://www.99freelas.com.br/login", locator)


def test_wait_for_projects_or_login_waits_for_links() -> None:
    first = FakeFirstLocator(raises_timeout=False)
    locator = cast("Locator", FakeWaitLocator(first))

    wait_for_projects_or_login("https://www.99freelas.com.br/projects", locator)

    assert first.wait_calls == [("attached", 15_000)]


def test_wait_for_projects_or_login_allows_missing_links() -> None:
    locator = cast("Locator", FakeWaitLocator(FakeFirstLocator(raises_timeout=True)))

    wait_for_projects_or_login("https://www.99freelas.com.br/projects", locator)


def test_collect_projects_deduplicates_urls() -> None:
    raw_text = "Title\nUseful description for card"
    links = FakeLinksLocator(
        [
            FakeLinkLocator("/project/a", raw_text),
            FakeLinkLocator("/project/a", raw_text),
            FakeLinkLocator(None, raw_text),
        ]
    )

    projects = collect_projects(cast("Locator", links))

    assert [project.project_url for project in projects] == [
        "https://www.99freelas.com.br/project/a"
    ]


def test_project_from_link_falls_back_to_link_text() -> None:
    locator = FakeLinkLocator("/project/empty", "Fallback title", [""])

    project = project_from_link(cast("Locator", locator))

    assert project.title == "Fallback title"


def test_nearest_project_text_prefers_long_ancestor_text() -> None:
    locator = FakeLinkLocator(None, "Link", ["short", "Detailed project card text"])

    assert (
        nearest_project_text(cast("Locator", locator)) == "Detailed project card text"
    )


def test_locator_text_or_empty_handles_timeout() -> None:
    locator = cast("Locator", FakeLinkLocator(None, "", timeout=True))

    assert locator_text_or_empty(locator) == ""


def test_small_text_helpers_cover_empty_branches() -> None:
    assert first_content_line(["projeto", "destaque"]) == ""
    assert first_matching_line(["abc"], r"R\$") is None
    assert extract_skills(["No labelled technologies here"]) == ()
    assert split_skill_values("Python, Python; Django|") == ["Python", "Django"]
    assert (
        build_description(["Title", "Body", "R$ 1"], "Title", "R$ 1", None, ())
        == "Body"
    )
