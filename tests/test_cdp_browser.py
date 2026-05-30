from __future__ import annotations

from typing import TYPE_CHECKING

from openfreela import cdp_browser

if TYPE_CHECKING:
    import pytest


class FakeSeleniumBaseCdp:
    """Fake SeleniumBase CDP module for launch option tests.

    Example:
        fake = FakeSeleniumBaseCdp()
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, dict[str, object]]] = []

    def Chrome(self, url: str | None = None, **kwargs: object) -> FakeCdpBrowser:
        """Capture a CDP Chrome launch call.

        Example:
            browser = fake.Chrome("https://example.com")
        """
        self.calls.append((url, kwargs))
        return FakeCdpBrowser()


class FakeCdpBrowser:
    """Fake CDP browser returned by SeleniumBase.

    Example:
        endpoint = FakeCdpBrowser().get_endpoint_url()
    """

    driver = object()

    def get_endpoint_url(self) -> str:
        """Return a fake CDP endpoint URL."""
        return "http://127.0.0.1:9222"


def test_launch_cdp_browser_uses_headed_chromium_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSeleniumBaseCdp()
    monkeypatch.setattr(cdp_browser, "sb_cdp", fake)

    launched = cdp_browser.launch_cdp_browser("https://example.com")

    assert launched.get_endpoint_url() == "http://127.0.0.1:9222"
    assert fake.calls == [
        (
            "https://example.com",
            {"use_chromium": True, "headless": False, "headed": True},
        )
    ]


def test_launch_cdp_browser_can_launch_headless(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSeleniumBaseCdp()
    monkeypatch.setattr(cdp_browser, "sb_cdp", fake)

    cdp_browser.launch_cdp_browser(headless=True)

    assert fake.calls == [
        (None, {"use_chromium": True, "headless": True, "headed": False})
    ]
