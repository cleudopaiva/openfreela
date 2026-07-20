from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Browser, BrowserContext, Locator, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from openfreela.browser.cdp import launch_cdp_browser
from openfreela.projects.model import FreelanceProject
from openfreela.sources.workana.html import (
    ParsedWorkanaProject,
    parse_project_item_html,
)

if TYPE_CHECKING:
    from pathlib import Path

SOURCE = "workana"
LOGIN_URL = "https://www.workana.com/"
PROJECTS_URL = "https://www.workana.com/pt/jobs?category=it-programming"
PROJECT_CARD_SELECTOR = ".project-item.js-project"
PAGINATION_LINK_SELECTOR = "ul.pagination a[href*='page=']"


def scrape_projects_pages(
    session_path: Path,
    *,
    headless: bool = True,
) -> list[FreelanceProject]:
    """Scrape all authenticated Workana IT/programming project pages.

    Example:
        projects = scrape_projects_pages(Path(".auth/workana.json"))
    """
    ensure_session_exists(session_path)
    cdp_browser = launch_cdp_browser(headless=headless)
    try:
        return scrape_connected_browser(cdp_browser.get_endpoint_url(), session_path)
    finally:
        cdp_browser.driver.stop()


def scrape_connected_browser(
    endpoint_url: str, session_path: Path
) -> list[FreelanceProject]:
    """Attach Playwright over CDP and scrape Workana projects.

    Example:
        projects = scrape_connected_browser("http://127.0.0.1:9222", Path("s.json"))
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(endpoint_url)
        context = browser_context_with_session(browser, session_path)
        projects = scrape_context_project_pages(context)
        browser.close()
        return projects


def scrape_context_project_pages(context: BrowserContext) -> list[FreelanceProject]:
    """Scrape and dedupe every paginated Workana projects page.

    Example:
        projects = scrape_context_project_pages(context)
    """
    page = context.new_page()
    projects = collect_projects_from_page(page, PROJECTS_URL)
    page_urls = pagination_page_urls(page)
    for page_url in page_urls[1:]:
        projects.extend(collect_projects_from_page(page, page_url))
    return dedupe_projects(projects)


def collect_projects_from_page(page: Page, page_url: str) -> list[FreelanceProject]:
    """Navigate to one Workana projects page and collect its project cards.

    Example:
        projects = collect_projects_from_page(page, PROJECTS_URL)
    """
    page.goto(page_url, wait_until="domcontentloaded")
    wait_for_project_cards(page.locator(PROJECT_CARD_SELECTOR))
    return collect_projects(page.locator(PROJECT_CARD_SELECTOR))


def pagination_page_urls(page: Page) -> list[str]:
    """Return Workana pagination URLs, always including the first page.

    Example:
        urls = pagination_page_urls(page)
    """
    urls = [PROJECTS_URL]
    links = page.locator(PAGINATION_LINK_SELECTOR)
    for index in range(links.count()):
        href = links.nth(index).get_attribute("href")
        if href:
            urls.append(urljoin(PROJECTS_URL, href))
    return dedupe_strings(urls) or [PROJECTS_URL]


def project_page_url(page_number: int) -> str:
    """Return the fallback Workana projects URL for one page number.

    Example:
        url = project_page_url(2)
    """
    if page_number < 1:
        raise ValueError(f"Invalid project page {page_number}; expected page >= 1.")
    if page_number == 1:
        return PROJECTS_URL
    return url_with_page(PROJECTS_URL, page_number)


def url_with_page(url: str, page_number: int) -> str:
    """Return a URL with its page query parameter set.

    Example:
        url = url_with_page(PROJECTS_URL, 2)
    """
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page_number)
    return urlunparse(parsed._replace(query=urlencode(query)))


def dedupe_strings(values: list[str]) -> list[str]:
    """Return strings deduplicated while preserving order.

    Example:
        values = dedupe_strings(["a", "a", "b"])
    """
    return list(dict.fromkeys(values))


def dedupe_projects(projects: list[FreelanceProject]) -> list[FreelanceProject]:
    """Return projects deduplicated by project URL while preserving order.

    Example:
        unique = dedupe_projects(projects)
    """
    unique_projects: list[FreelanceProject] = []
    seen_urls: set[str] = set()
    for project in projects:
        if project.project_url is None or project.project_url in seen_urls:
            continue
        seen_urls.add(project.project_url)
        unique_projects.append(project)
    return unique_projects


def browser_context_with_session(
    browser: Browser,
    session_path: Path,
) -> BrowserContext:
    """Create a Playwright context using saved storage state.

    Example:
        context = browser_context_with_session(browser, Path("s.json"))
    """
    try:
        return browser.new_context(storage_state=str(session_path))
    except PlaywrightError:
        return browser.contexts[0]


def ensure_session_exists(session_path: Path) -> None:
    """Fail early when the scraper has no Workana session to reuse.

    Example:
        ensure_session_exists(Path(".auth/workana.json"))
    """
    if session_path.exists():
        return
    message = f"Missing session file {session_path}; run login-workana first."
    raise FileNotFoundError(message)


def wait_for_project_cards(cards: Locator) -> None:
    """Wait for Workana project cards before parsing the page.

    Example:
        wait_for_project_cards(page.locator(".project-item"))
    """
    try:
        cards.first.wait_for(state="attached", timeout=15_000)
    except PlaywrightTimeoutError as error:
        message = "No Workana project cards found; check login and listing URL."
        raise RuntimeError(message) from error


def collect_projects(cards: Locator) -> list[FreelanceProject]:
    """Collect unique projects from Workana project card locators.

    Example:
        projects = collect_projects(page.locator(".project-item"))
    """
    projects: list[FreelanceProject] = []
    for index in range(cards.count()):
        project = project_from_card(cards.nth(index))
        if project is not None:
            projects.append(project)
    return dedupe_projects(projects)


def project_from_card(card: Locator) -> FreelanceProject | None:
    """Build one project from a Workana project card node.

    Example:
        project = project_from_card(page.locator(".project-item").first)
    """
    item = parse_project_item_html(locator_outer_html(card))
    if item is None:
        return None
    return project_from_parsed_item(item)


def project_from_parsed_item(item: ParsedWorkanaProject) -> FreelanceProject:
    """Convert parsed Workana fields into the public project model.

    Example:
        project = project_from_parsed_item(item)
    """
    return FreelanceProject(
        item.title,
        item.description,
        item.budget,
        item.skills,
        absolute_project_url(item.project_href),
        item.posted_at,
        None,
        item.proposals,
        None,
        None,
        item.raw_text,
        SOURCE,
    )


def absolute_project_url(href: str | None) -> str | None:
    """Normalize Workana project hrefs into absolute URLs.

    Example:
        url = absolute_project_url("/job/foo")
    """
    if href is None or not href.strip():
        return None
    return urljoin(LOGIN_URL, href)


def locator_outer_html(locator: Locator) -> str:
    """Read a locator's outerHTML while tolerating missing nodes.

    Example:
        html = locator_outer_html(page.locator(".project-item").first)
    """
    try:
        return str(locator.evaluate("element => element.outerHTML", timeout=1_000))
    except (AttributeError, PlaywrightError):
        return ""
