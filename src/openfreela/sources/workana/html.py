from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass(frozen=True)
class ParsedWorkanaProject:
    """Project fields parsed from a Workana project card.

    Example:
        item = ParsedWorkanaProject("Title", "Desc", None, (), None, None, None, "")
    """

    title: str
    description: str
    budget: str | None
    skills: tuple[str, ...]
    project_href: str | None
    posted_at: str | None
    proposals: int | None
    raw_text: str


@dataclass
class TagState:
    """Parser state that must be reverted when a tag closes.

    Example:
        state = TagState(description=True)
    """

    title_root: bool = False
    title_link: bool = False
    description: bool = False
    skipped_description: bool = False
    skill: bool = False
    posted_at: bool = False
    bids: bool = False
    budget: bool = False


@dataclass
class WorkanaProjectHtmlParser(HTMLParser):
    """Parse Workana project card markup.

    Example:
        parser = WorkanaProjectHtmlParser()
    """

    stack: list[TagState] = field(default_factory=list)
    title_parts: list[str] = field(default_factory=list)
    description_parts: list[str] = field(default_factory=list)
    visible_parts: list[str] = field(default_factory=list)
    skill_values: list[str] = field(default_factory=list)
    date_parts: list[str] = field(default_factory=list)
    bid_parts: list[str] = field(default_factory=list)
    budget_parts: list[str] = field(default_factory=list)
    current_skill_parts: list[str] | None = None
    title_attr: str | None = None
    project_href: str | None = None
    title_depth: int = 0
    title_link_depth: int = 0
    description_depth: int = 0
    skipped_description_depth: int = 0
    date_depth: int = 0
    bid_depth: int = 0
    budget_depth: int = 0

    def __post_init__(self) -> None:
        """Initialize the base HTML parser state."""
        super().__init__()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track parser contexts opened by a start tag."""
        state = self.start_state(tag, attrs)
        self.stack.append(state)
        if tag == "br" and self.description_depth:
            self.description_parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Treat self-closing tags as a short-lived start tag."""
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        """Revert parser contexts closed by an end tag."""
        del tag
        if self.stack:
            self.end_state(self.stack.pop())

    def handle_data(self, data: str) -> None:
        """Capture text for active parser contexts."""
        self.visible_parts.append(data)
        if self.title_link_depth:
            self.title_parts.append(data)
        if self.description_depth and not self.skipped_description_depth:
            self.description_parts.append(data)
        if self.current_skill_parts is not None:
            self.current_skill_parts.append(data)
        if self.date_depth:
            self.date_parts.append(data)
        if self.bid_depth:
            self.bid_parts.append(data)
        if self.budget_depth:
            self.budget_parts.append(data)

    def project_item(self) -> ParsedWorkanaProject | None:
        """Return parsed project fields when the HTML contains project data."""
        title = clean_html_text(self.title_attr or " ".join(self.title_parts))
        description = clean_description(" ".join(self.description_parts))
        raw_text = clean_html_text(" ".join(self.visible_parts))
        if not title and not description and self.project_href is None:
            return None
        return ParsedWorkanaProject(
            title,
            description,
            clean_optional_text(" ".join(self.budget_parts)),
            tuple(dict.fromkeys(self.skill_values)),
            self.project_href,
            clean_posted_at(" ".join(self.date_parts)),
            proposals_from_text(" ".join(self.bid_parts)),
            raw_text,
        )

    def start_state(self, tag: str, attrs: list[tuple[str, str | None]]) -> TagState:
        """Create and apply parser state for one start tag."""
        classes = attribute_classes(attrs)
        state = TagState()
        self.track_title(tag, attrs, classes, state)
        self.track_description(tag, classes, state)
        self.track_skill(tag, classes, state)
        self.track_metadata(tag, classes, state)
        self.track_budget(tag, classes, state)
        return state

    def end_state(self, state: TagState) -> None:
        """Undo one tag state from parser counters."""
        if state.skill:
            self.finish_current_skill()
        self.title_depth -= int(state.title_root)
        self.title_link_depth -= int(state.title_link)
        self.description_depth -= int(state.description)
        self.skipped_description_depth -= int(state.skipped_description)
        self.date_depth -= int(state.posted_at)
        self.bid_depth -= int(state.bids)
        self.budget_depth -= int(state.budget)

    def track_title(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        classes: set[str],
        state: TagState,
    ) -> None:
        """Track project title anchors and full title attributes."""
        if tag == "h2" and "project-title" in classes:
            state.title_root = True
            self.title_depth += 1
        if tag == "span" and self.title_depth:
            self.title_attr = self.title_attr or attribute_value(attrs, "title")
        if tag == "a" and self.title_depth:
            state.title_link = True
            self.title_link_depth += 1
            self.project_href = self.project_href or attribute_value(attrs, "href")

    def track_description(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track Workana's project preview and skip expand controls."""
        if tag == "p" and "text-expander-content" in classes:
            state.description = True
            self.description_depth += 1
        if self.description_depth and tag == "a" and "link" in classes:
            state.skipped_description = True
            self.skipped_description_depth += 1

    def track_skill(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track one Workana skill link."""
        if tag != "a" or "skill" not in classes:
            return
        state.skill = True
        self.current_skill_parts = []

    def track_metadata(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track posted date and proposal count spans."""
        if tag == "span" and "date" in classes:
            state.posted_at = True
            self.date_depth += 1
        if tag == "span" and "bids" in classes:
            state.bids = True
            self.bid_depth += 1

    def track_budget(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track Workana budget text."""
        if tag == "p" and "budget" in classes:
            state.budget = True
            self.budget_depth += 1

    def finish_current_skill(self) -> None:
        """Store the current skill text and clear its buffer."""
        value = clean_html_text(" ".join(self.current_skill_parts or []))
        if value:
            self.skill_values.append(value)
        self.current_skill_parts = None


def parse_project_item_html(html: str) -> ParsedWorkanaProject | None:
    """Parse one Workana project card HTML string.

    Example:
        item = parse_project_item_html('<div class="project-item"></div>')
    """
    parser = WorkanaProjectHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.project_item()


def attribute_classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    """Return the class names from an HTML attribute list.

    Example:
        classes = attribute_classes([("class", "title active")])
    """
    value = attribute_value(attrs, "class") or ""
    return {part for part in value.split() if part}


def attribute_value(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    """Return one HTML attribute value by name.

    Example:
        href = attribute_value([("href", "/job/a")], "href")
    """
    for attr_name, value in attrs:
        if attr_name == name:
            return value
    return None


def clean_html_text(text: str) -> str:
    """Normalize whitespace from parsed HTML text.

    Example:
        assert clean_html_text("a\n\n b") == "a b"
    """
    return re.sub(r"\s+", " ", text).strip()


def clean_description(text: str) -> str:
    """Return Workana description text without expand controls.

    Example:
        description = clean_description("Build API ... Ver mais detalhes")
    """
    value = re.sub(r"\s*\.\.\.\s*$", "", clean_html_text(text))
    return value.replace(" ...", "").strip()


def clean_optional_text(text: str) -> str | None:
    """Return normalized text or None when empty.

    Example:
        assert clean_optional_text(" ") is None
    """
    value = clean_html_text(text)
    return value or None


def clean_posted_at(text: str) -> str | None:
    """Return Workana posted-at text without the field label.

    Example:
        posted_at = clean_posted_at("Publicado: há 3 horas")
    """
    value = clean_html_text(text).removeprefix("Publicado:").strip()
    return value or None


def proposals_from_text(text: str) -> int | None:
    """Return Workana proposal count from metadata text.

    Example:
        proposals = proposals_from_text("Propostas: 19")
    """
    match = re.search(r"Propostas:\s*(\d+)", text, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))
