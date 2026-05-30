from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, sync_playwright

from openfreela.cdp_browser import launch_cdp_browser

LOGIN_URL = "https://www.99freelas.com.br/login"
DEFAULT_SESSION_PATH = Path(".auth/99freelas.json")


def save_manual_login_session(session_path: Path) -> None:
    """Save a manual 99freelas login session for later scraper runs.

    Example:
        save_manual_login_session(Path(".auth/99freelas.json"))
    """
    session_path.parent.mkdir(parents=True, exist_ok=True)
    cdp_browser = launch_cdp_browser(LOGIN_URL)
    try:
        save_connected_playwright_session(cdp_browser.get_endpoint_url(), session_path)
    finally:
        cdp_browser.driver.stop()


def save_connected_playwright_session(endpoint_url: str, session_path: Path) -> None:
    """Attach Playwright over CDP and save the active browser context.

    Example:
        save_connected_playwright_session("http://127.0.0.1:9222", Path("s.json"))
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(endpoint_url)
        context = first_browser_context(browser)
        wait_for_login_confirmation()
        context.storage_state(path=str(session_path))
        browser.close()


def first_browser_context(browser: Browser) -> BrowserContext:
    """Return the default browser context created by CDP.

    Example:
        context = first_browser_context(browser)
    """
    if browser.contexts:
        return browser.contexts[0]
    message = "CDP browser has no contexts; expected SeleniumBase default context."
    raise RuntimeError(message)


def wait_for_login_confirmation() -> None:
    """Wait until the user confirms the manual browser login is complete.

    Example:
        wait_for_login_confirmation()
    """
    message = "Log in manually, then press Enter here to save the session..."
    input(message)
