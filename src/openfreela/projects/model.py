from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreelanceProject:
    """A project extracted from a freelance project listing.

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
    source: str = "unknown"

    def to_dict(self) -> dict[str, str | int | list[str] | None]:
        """Return a JSON-serializable project dictionary.

        Example:
            payload = project.to_dict()
        """
        return {
            "source": self.source,
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
