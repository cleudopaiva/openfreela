from __future__ import annotations

from typing import Protocol, cast

from seleniumbase import sb_cdp  # type: ignore[import-untyped]


class CdpBrowserDriver(Protocol):
    """Driver handle owned by a SeleniumBase CDP browser.

    Example:
        cdp_browser.driver.stop()
    """

    def stop(self) -> None:
        """Stop the launched CDP browser."""


class CdpBrowser(Protocol):
    """SeleniumBase CDP browser facade used by Playwright.

    Example:
        endpoint = cdp_browser.get_endpoint_url()
    """

    driver: CdpBrowserDriver

    def get_endpoint_url(self) -> str:
        """Return the browser remote-debugging endpoint URL."""


def launch_cdp_browser(url: str | None = None, *, headless: bool = False) -> CdpBrowser:
    """Launch stealth Chromium with SeleniumBase CDP mode.

    Example:
        cdp_browser = launch_cdp_browser("https://example.com")
    """
    kwargs = {"use_chromium": True, "headless": headless, "headed": not headless}
    if url is None:
        return cast("CdpBrowser", sb_cdp.Chrome(**kwargs))
    return cast("CdpBrowser", sb_cdp.Chrome(url, **kwargs))
