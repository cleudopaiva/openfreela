from __future__ import annotations

from openfreela.projects.model import FreelanceProject


def test_freelance_project_to_dict_includes_source() -> None:
    project = FreelanceProject(
        "Title",
        "Desc",
        None,
        ("Python",),
        "https://example.com/job",
        None,
        None,
        None,
        None,
        None,
        "raw",
        "workana",
    )

    assert project.to_dict()["source"] == "workana"
    assert project.to_dict()["skills"] == ["Python"]
