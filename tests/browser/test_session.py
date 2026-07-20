from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from openfreela.browser import session as browser_session

if TYPE_CHECKING:
    from pathlib import Path

    from playwright.sync_api import Browser


class FakeCdpDriver:
    """Fake CDP browser driver for session tests.

    Example:
        driver = FakeCdpDriver()
    """

    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        """Record that the browser was stopped."""
        self.stopped = True


class FakeCdpBrowser:
    """Fake SeleniumBase browser for session tests.

    Example:
        browser = FakeCdpBrowser()
    """

    def __init__(self) -> None:
        self.driver = FakeCdpDriver()

    def get_endpoint_url(self) -> str:
        """Return a fake CDP endpoint."""
        return "http://127.0.0.1:9222"


class FakeBrowser:
    """Fake Playwright browser with configurable contexts.

    Example:
        browser = FakeBrowser([object()])
    """

    def __init__(self, contexts: list[object]) -> None:
        self.contexts = contexts


def test_save_manual_login_session_stops_cdp_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cdp_browser = FakeCdpBrowser()
    endpoints: list[tuple[str, Path]] = []

    opened_urls: list[str] = []

    def launch_browser(url: str) -> FakeCdpBrowser:
        opened_urls.append(url)
        return cdp_browser

    monkeypatch.setattr(
        browser_session,
        "launch_cdp_browser",
        launch_browser,
    )
    monkeypatch.setattr(
        browser_session,
        "save_connected_playwright_session",
        lambda endpoint, path: endpoints.append((endpoint, path)),
    )

    session_path = tmp_path / ".auth" / "99freelas.json"
    browser_session.save_manual_login_session(session_path, "https://example.com/login")

    assert endpoints == [("http://127.0.0.1:9222", session_path)]
    assert opened_urls == ["https://example.com/login"]
    assert cdp_browser.driver.stopped
    assert session_path.parent.exists()


def test_first_browser_context_returns_existing_context() -> None:
    context = object()
    browser = cast("Browser", FakeBrowser([context]))

    assert browser_session.first_browser_context(browser) is context


def test_first_browser_context_rejects_missing_contexts() -> None:
    browser = cast("Browser", FakeBrowser([]))

    with pytest.raises(RuntimeError, match="expected SeleniumBase default context"):
        browser_session.first_browser_context(browser)
