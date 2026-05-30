from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

NOISY_DESCRIPTION_CLASSES = {"read-more", "read-less", "more-link", "less-link"}


@dataclass(frozen=True)
class ParsedProjectItem:
    """Project fields parsed from a 99freelas result-item HTML block.

    Example:
        item = ParsedProjectItem(
            "Title", "Desc", None, (), None, None, None, None, None, None, "raw"
        )
    """

    title: str
    description: str
    budget: str | None
    skills: tuple[str, ...]
    project_href: str | None
    posted_at: str | None
    remaining_time: str | None
    proposals: int | None
    interested: int | None
    level: str | None
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
    information: bool = False
    posted_at: bool = False
    remaining_time: bool = False


@dataclass
class ResultItemHtmlParser(HTMLParser):
    """Parse the 99freelas project result-item markup.

    Example:
        parser = ResultItemHtmlParser()
    """

    stack: list[TagState] = field(default_factory=list)
    title_parts: list[str] = field(default_factory=list)
    description_parts: list[str] = field(default_factory=list)
    information_parts: list[str] = field(default_factory=list)
    posted_at_parts: list[str] = field(default_factory=list)
    remaining_time_parts: list[str] = field(default_factory=list)
    visible_parts: list[str] = field(default_factory=list)
    skill_values: list[str] = field(default_factory=list)
    current_skill_parts: list[str] | None = None
    project_href: str | None = None
    title_depth: int = 0
    title_link_depth: int = 0
    description_depth: int = 0
    skipped_description_depth: int = 0
    information_depth: int = 0
    posted_at_depth: int = 0
    remaining_time_depth: int = 0

    def __post_init__(self) -> None:
        """Initialize the base HTML parser state."""
        super().__init__()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track parser contexts opened by a start tag."""
        state = self.start_state(tag, attrs)
        self.stack.append(state)
        if tag == "br":
            self.add_description_separator()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Treat self-closing tags as a short-lived start tag."""
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        """Revert parser contexts closed by an end tag."""
        del tag
        if not self.stack:
            return
        self.end_state(self.stack.pop())

    def handle_data(self, data: str) -> None:
        """Capture text for active parser contexts."""
        self.visible_parts.append(data)
        if self.title_link_depth:
            self.title_parts.append(data)
        if self.description_depth and not self.skipped_description_depth:
            self.description_parts.append(data)
        if self.information_depth:
            self.information_parts.append(data)
        if self.current_skill_parts is not None:
            self.current_skill_parts.append(data)
        if self.posted_at_depth:
            self.posted_at_parts.append(data)
        if self.remaining_time_depth:
            self.remaining_time_parts.append(data)

    def project_item(self) -> ParsedProjectItem | None:
        """Return parsed project fields when the HTML contains project data."""
        title = clean_html_text(" ".join(self.title_parts))
        description = clean_html_text(" ".join(self.description_parts))
        information = clean_html_text(" ".join(self.information_parts))
        raw_text = clean_html_text(" ".join(self.visible_parts))
        if not title and not description and self.project_href is None:
            return None
        return ParsedProjectItem(
            title,
            description,
            first_matching_text(raw_text, r"R\$|orçamento|budget|a combinar"),
            tuple(dict.fromkeys(self.skill_values)),
            self.project_href,
            clean_optional_text(" ".join(self.posted_at_parts)),
            clean_optional_text(" ".join(self.remaining_time_parts)),
            labelled_int(information, "Propostas"),
            labelled_int(information, "Interessados"),
            information_level(information),
            raw_text,
        )

    def start_state(self, tag: str, attrs: list[tuple[str, str | None]]) -> TagState:
        """Create and apply parser state for one start tag."""
        classes = attribute_classes(attrs)
        state = TagState()
        self.track_title(tag, attrs, classes, state)
        self.track_description(tag, classes, state)
        self.track_skill(tag, classes, state)
        self.track_information(tag, classes, state)
        self.track_posted_at(tag, classes, state)
        self.track_remaining_time(tag, classes, state)
        return state

    def end_state(self, state: TagState) -> None:
        """Undo one tag state from parser counters."""
        if state.skill:
            self.finish_current_skill()
        self.title_depth -= int(state.title_root)
        self.title_link_depth -= int(state.title_link)
        self.description_depth -= int(state.description)
        self.skipped_description_depth -= int(state.skipped_description)
        self.information_depth -= int(state.information)
        self.posted_at_depth -= int(state.posted_at)
        self.remaining_time_depth -= int(state.remaining_time)

    def track_title(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        classes: set[str],
        state: TagState,
    ) -> None:
        """Track title roots and project title anchors."""
        if tag == "h1" and "title" in classes:
            state.title_root = True
            self.title_depth += 1
        if tag != "a" or not self.title_depth:
            return
        state.title_link = True
        self.title_link_depth += 1
        self.project_href = self.project_href or attribute_value(attrs, "href")

    def track_description(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track the project description and noisy expand/collapse nodes."""
        if tag == "div" and "description" in classes:
            state.description = True
            self.description_depth += 1
        if self.description_depth and classes & NOISY_DESCRIPTION_CLASSES:
            state.skipped_description = True
            self.skipped_description_depth += 1

    def track_skill(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track one skill link."""
        if tag != "a" or "habilidade" not in classes:
            return
        state.skill = True
        self.current_skill_parts = []

    def track_information(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track the project metadata information paragraph."""
        if tag == "p" and "information" in classes:
            state.information = True
            self.information_depth += 1

    def track_posted_at(self, tag: str, classes: set[str], state: TagState) -> None:
        """Track the published-at timestamp element."""
        if tag == "b" and "datetime" in classes:
            state.posted_at = True
            self.posted_at_depth += 1

    def track_remaining_time(
        self, tag: str, classes: set[str], state: TagState
    ) -> None:
        """Track the project remaining-time timestamp element."""
        if tag == "b" and "datetime-restante" in classes:
            state.remaining_time = True
            self.remaining_time_depth += 1

    def add_description_separator(self) -> None:
        """Preserve paragraph boundaries inside description text."""
        if self.description_depth and not self.skipped_description_depth:
            self.description_parts.append("\n")

    def finish_current_skill(self) -> None:
        """Store the current skill text and clear its buffer."""
        value = clean_html_text(" ".join(self.current_skill_parts or []))
        if value:
            self.skill_values.append(value)
        self.current_skill_parts = None


def parse_result_item_html(html: str) -> ParsedProjectItem | None:
    """Parse one 99freelas result-item HTML string.

    Example:
        item = parse_result_item_html('<li class="result-item"></li>')
    """
    parser = ResultItemHtmlParser()
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
        href = attribute_value([("href", "/project/a")], "href")
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


def clean_optional_text(text: str) -> str | None:
    """Return normalized text or None when empty.

    Example:
        assert clean_optional_text(" ") is None
    """
    value = clean_html_text(text)
    return value or None


def first_matching_text(text: str, pattern: str) -> str | None:
    """Return the first sentence-like text fragment matching a pattern.

    Example:
        budget = first_matching_text("Valor R$ 500 Publicado", r"R\\$")
    """
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        if re.search(pattern, part, flags=re.IGNORECASE):
            return clean_html_text(part)
    return None


def labelled_int(text: str, label: str) -> int | None:
    """Return an integer that appears after a labelled metadata field.

    Example:
        proposals = labelled_int("Propostas: 10", "Propostas")
    """
    match = re.search(rf"{re.escape(label)}:\s*(\d+)", text, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def information_level(text: str) -> str | None:
    """Return the project level from a 99freelas information paragraph.

    Example:
        level = information_level("Web | Intermediário | Publicado: hoje")
    """
    parts = [clean_html_text(part) for part in text.split("|")]
    candidates = [part for part in parts if part and "Publicado:" not in part]
    if len(candidates) < 2:
        return None
    return candidates[1]
