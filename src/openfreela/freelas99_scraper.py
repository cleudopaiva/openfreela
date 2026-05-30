from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Browser, BrowserContext, Locator, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from openfreela.cdp_browser import launch_cdp_browser
from openfreela.freelas99_html import ParsedProjectItem, parse_result_item_html

PROJECTS_URL = "https://www.99freelas.com.br/projects?categoria=web-mobile-e-software"
PROJECT_LINK_SELECTOR = (
    "li.result-item h1.title a[href*='/project/'], "
    "li.result-item h1.title a[href*='/projeto/'], "
    "h1.title a[href*='/project/'], "
    "h1.title a[href*='/projeto/']"
)
RESULT_ITEM_SELECTOR = (
    "xpath=ancestor::li[contains(concat(' ', normalize-space(@class), ' '), "
    "' result-item ')][1]"
)
LAST_PAGE_SELECTOR = ".pagination-component .go-to-last-page[data-page]"
MAX_PROJECT_LINKS = 80

if TYPE_CHECKING:
    from pathlib import Path


class SessionExpiredError(RuntimeError):
    """Raised when the saved 99freelas session no longer opens projects."""


@dataclass(frozen=True)
class FreelanceProject:
    """A project extracted from the 99freelas project listing.

    Example:
        project = FreelanceProject(
            "API", "Build API", None, (), None, None, None, None, None, None, "API"
        )
    """

    title: str
    description: str
    budget: str | None
    skills: tuple[str, ...]
    project_url: str | None
    posted_at: str | None
    remaining_time: str | None
    proposals: int | None
    interested: int | None
    level: str | None
    raw_text: str

    def to_dict(self) -> dict[str, str | int | list[str] | None]:
        """Return a JSON-serializable project dictionary.

        Example:
            payload = project.to_dict()
        """
        return {
            "title": self.title,
            "description": self.description,
            "budget": self.budget,
            "skills": list(self.skills),
            "project_url": self.project_url,
            "posted_at": self.posted_at,
            "remaining_time": self.remaining_time,
            "proposals": self.proposals,
            "interested": self.interested,
            "level": self.level,
            "raw_text": self.raw_text,
        }


def scrape_projects_pages(
    session_path: Path,
    *,
    headless: bool = True,
) -> list[FreelanceProject]:
    """Scrape all authenticated 99freelas software project pages.

    Example:
        projects = scrape_projects_pages(Path(".auth/99freelas.json"))
    """
    ensure_session_exists(session_path)
    cdp_browser = launch_cdp_browser(headless=headless)
    try:
        return scrape_connected_browser(cdp_browser.get_endpoint_url(), session_path)
    finally:
        cdp_browser.driver.stop()


def scrape_first_projects_page(
    session_path: Path,
    *,
    headless: bool = True,
) -> list[FreelanceProject]:
    """Compatibility wrapper for scraping all software project pages.

    Example:
        projects = scrape_first_projects_page(Path(".auth/99freelas.json"))
    """
    return scrape_projects_pages(session_path, headless=headless)


def scrape_connected_browser(
    endpoint_url: str, session_path: Path
) -> list[FreelanceProject]:
    """Attach Playwright over CDP and scrape the projects page.

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
    """Scrape and dedupe every paginated software projects page.

    Example:
        projects = scrape_context_project_pages(context)
    """
    page = context.new_page()
    projects = collect_projects_from_page(page, 1)
    last_page = last_projects_page(page)
    for page_number in range(2, last_page + 1):
        projects.extend(collect_projects_from_page(page, page_number))
    return dedupe_projects(projects)


def collect_projects_from_page(page: Page, page_number: int) -> list[FreelanceProject]:
    """Navigate to one projects page and collect its project cards.

    Example:
        projects = collect_projects_from_page(page, 2)
    """
    page.goto(project_page_url(page_number), wait_until="domcontentloaded")
    wait_for_projects_or_login(page.url, page.locator(PROJECT_LINK_SELECTOR))
    return collect_projects(page.locator(PROJECT_LINK_SELECTOR))


def last_projects_page(page: Page) -> int:
    """Return the last projects page number from the pagination component.

    Example:
        count = last_projects_page(page)
    """
    try:
        locator = page.locator(LAST_PAGE_SELECTOR)
        if locator.count() == 0:
            return 1
        value = locator.first.get_attribute("data-page", timeout=1_000)
    except PlaywrightError, PlaywrightTimeoutError:
        return 1
    return positive_int_or_default(value, 1)


def project_page_url(page_number: int) -> str:
    """Return the software category URL for one page number.

    Example:
        url = project_page_url(2)
    """
    if page_number < 1:
        message = f"Invalid project page {page_number}; expected page >= 1."
        raise ValueError(message)
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


def positive_int_or_default(value: str | None, default: int) -> int:
    """Parse a positive integer or return the provided default.

    Example:
        page = positive_int_or_default("37", 1)
    """
    if value is None or not value.isdecimal():
        return default
    return max(int(value), default)


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
    """Fail early when the scraper has no session to reuse.

    Example:
        ensure_session_exists(Path(".auth/99freelas.json"))
    """
    if session_path.exists():
        return
    message = f"Missing session file {session_path}; run login-99freelas first."
    raise FileNotFoundError(message)


def wait_for_projects_or_login(page_url: str, links: Locator) -> None:
    """Wait for project links and reject expired login sessions.

    Example:
        wait_for_projects_or_login(page.url, page.locator("a"))
    """
    if is_login_url(page_url):
        raise SessionExpiredError("Session expired; run login-99freelas again.")
    try:
        links.first.wait_for(state="attached", timeout=15_000)
    except PlaywrightTimeoutError:
        return


def is_login_url(url: str) -> bool:
    """Return whether a URL points to the 99freelas login page.

    Example:
        assert is_login_url("https://www.99freelas.com.br/login")
    """
    return "/login" in url


def collect_projects(links: Locator) -> list[FreelanceProject]:
    """Collect unique project cards from project link locators.

    Example:
        projects = collect_projects(page.locator("a[href*='/project']"))
    """
    projects: list[FreelanceProject] = []
    seen_urls: set[str] = set()
    count = min(links.count(), MAX_PROJECT_LINKS)
    for index in range(count):
        project = project_from_link(links.nth(index))
        if project.project_url is None or project.project_url in seen_urls:
            continue
        seen_urls.add(project.project_url)
        projects.append(project)
    return projects


def project_from_link(link: Locator) -> FreelanceProject:
    """Build one project model from a project link and its nearest card text.

    Example:
        project = project_from_link(page.locator("a").first)
    """
    structured_project = project_from_result_item(link.locator(RESULT_ITEM_SELECTOR))
    if structured_project is not None:
        return structured_project
    href = link.get_attribute("href")
    project_url = absolute_project_url(href)
    raw_text = nearest_project_text(link)
    project = parse_project_card_text(raw_text, project_url)
    if project.title:
        return project
    title = clean_text(link.inner_text(timeout=1_000))
    return FreelanceProject(
        title,
        project.description,
        project.budget,
        project.skills,
        project_url,
        project.posted_at,
        project.remaining_time,
        project.proposals,
        project.interested,
        project.level,
        raw_text,
    )


def project_from_result_item(card: Locator) -> FreelanceProject | None:
    """Build one project from a structured 99freelas result-item node.

    Example:
        project = project_from_result_item(page.locator("li.result-item").first)
    """
    item = parse_result_item_html(locator_outer_html(card))
    if item is None:
        return None
    return project_from_parsed_item(item)


def project_from_parsed_item(item: ParsedProjectItem) -> FreelanceProject:
    """Convert parsed HTML fields into the public project model.

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
        item.remaining_time,
        item.proposals,
        item.interested,
        item.level,
        item.raw_text,
    )


def locator_outer_html(locator: Locator) -> str:
    """Read a locator's outerHTML while tolerating missing structured nodes.

    Example:
        html = locator_outer_html(page.locator("li.result-item").first)
    """
    try:
        return str(locator.evaluate("element => element.outerHTML", timeout=1_000))
    except AttributeError, PlaywrightError:
        return ""


def absolute_project_url(href: str | None) -> str | None:
    """Normalize project hrefs into absolute URLs.

    Example:
        url = absolute_project_url("/project/foo")
    """
    if href is None or not href.strip():
        return None
    return urljoin(PROJECTS_URL, href)


def nearest_project_text(link: Locator) -> str:
    """Return visible text from the nearest likely project card.

    Example:
        text = nearest_project_text(page.locator("a").first)
    """
    for selector in card_ancestor_selectors():
        text = locator_text_or_empty(link.locator(selector))
        if len(text) >= 20:
            return text
    return locator_text_or_empty(link)


def card_ancestor_selectors() -> tuple[str, ...]:
    """Return ancestor selectors ordered from specific to generic.

    Example:
        selectors = card_ancestor_selectors()
    """
    return (
        "xpath=ancestor::article[1]",
        "xpath=ancestor::li[1]",
        "xpath=ancestor::*[contains(@class, 'project')][1]",
        "xpath=ancestor::div[1]",
    )


def locator_text_or_empty(locator: Locator) -> str:
    """Read locator text while tolerating missing nodes.

    Example:
        text = locator_text_or_empty(page.locator("main"))
    """
    try:
        return clean_text(locator.inner_text(timeout=1_000))
    except PlaywrightTimeoutError:
        return ""


def parse_project_card_text(raw_text: str, project_url: str | None) -> FreelanceProject:
    """Parse normalized card text into a project model.

    Example:
        project = parse_project_card_text("Site\nR$ 500", "https://example.com")
    """
    lines = normalized_lines(raw_text)
    title = first_content_line(lines)
    budget = first_matching_line(lines, r"R\$|orçamento|budget|a combinar")
    posted_at = first_matching_line(lines, r"há \d+|publicado|posted|hoje|ontem")
    skills = extract_skills(lines)
    description = build_description(lines, title, budget, posted_at, skills)
    return FreelanceProject(
        title,
        description,
        budget,
        skills,
        project_url,
        posted_at,
        None,
        None,
        None,
        None,
        clean_text(raw_text),
    )


def normalized_lines(raw_text: str) -> list[str]:
    """Split text into useful non-empty lines.

    Example:
        lines = normalized_lines(" A \n\n B ")
    """
    return [clean_text(line) for line in raw_text.splitlines() if clean_text(line)]


def clean_text(text: str) -> str:
    """Normalize whitespace in scraped text.

    Example:
        assert clean_text("a   b") == "a b"
    """
    return re.sub(r"\s+", " ", text).strip()


def first_content_line(lines: list[str]) -> str:
    """Return the first line that looks like project content.

    Example:
        title = first_content_line(["Projeto Python"])
    """
    ignored = {"projeto", "projetos", "novo", "destaque"}
    for line in lines:
        if line.casefold() not in ignored:
            return line
    return ""


def first_matching_line(lines: list[str], pattern: str) -> str | None:
    r"""Return the first line matching a case-insensitive pattern.

    Example:
        budget = first_matching_line(["R$ 500"], r"R\$")
    """
    for line in lines:
        if re.search(pattern, line, flags=re.IGNORECASE):
            return line
    return None


def extract_skills(lines: list[str]) -> tuple[str, ...]:
    """Extract skills from labelled card lines when available.

    Example:
        skills = extract_skills(["Habilidades: Python, Django"])
    """
    for line in lines:
        if not re.search(r"habilidades|skills|tags", line, flags=re.IGNORECASE):
            continue
        _, _, values = line.partition(":")
        return tuple(split_skill_values(values or line))
    return ()


def split_skill_values(text: str) -> list[str]:
    """Split a labelled skills string into unique skill names.

    Example:
        values = split_skill_values("Python, Django")
    """
    values = [clean_text(value) for value in re.split(r"[,;|]", text)]
    return [value for value in dict.fromkeys(values) if value]


def build_description(
    lines: list[str],
    title: str,
    budget: str | None,
    posted_at: str | None,
    skills: tuple[str, ...],
) -> str:
    """Build a concise description from remaining card lines.

    Example:
        description = build_description(["Title", "Body"], "Title", None, None, ())
    """
    blocked = {title, budget, posted_at, *skills, ""}
    usable = [line for line in lines if line not in blocked]
    return " ".join(usable[:4])
