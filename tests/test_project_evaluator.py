from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from openfreela.project_evaluator import (
    EvaluationRunConfig,
    ProjectEvaluation,
    evaluate_project_file,
    load_json_object,
    notification_message,
    parse_project_evaluation,
    render_prompt,
    should_notify,
)

if TYPE_CHECKING:
    from pathlib import Path


class FakeJudge:
    """Fake AI judge that returns preconfigured JSON content.

    Example:
        judge = FakeJudge('{"recommendation": "apply"}')
    """

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def chat_json(self, prompt: str) -> str:
        """Record the prompt and return the fake response."""
        self.prompts.append(prompt)
        return self.response


class FakeNotifier:
    """Fake notifier that records messages.

    Example:
        notifier = FakeNotifier()
    """

    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(self, text: str) -> None:
        """Record one notification message."""
        self.messages.append(text)


def project_payload() -> dict[str, object]:
    """Return a minimal scraped project payload for tests.

    Example:
        project = project_payload()
    """
    return {"title": "API Project", "project_url": "https://example.com/project"}


def ai_payload(
    *,
    profile_score: int = 80,
    recommendation: str = "apply",
) -> dict[str, object]:
    """Return a complete fake AI response payload.

    Example:
        payload = ai_payload(profile_score=90)
    """
    return {
        "profile_match_score": profile_score,
        "execution_confidence_score": 70,
        "recommendation": recommendation,
        "summary": "Good fit",
        "why_apply": "Strong Python/API overlap",
        "cv_matches": ["Python"],
        "adjacent_skills": ["FastAPI"],
        "missing_skills": ["Domain details"],
        "risks": ["Scope unclear"],
        "proposal_angle": "Lead with API delivery experience",
    }


def test_render_prompt_injects_cv_and_project_json() -> None:
    prompt = render_prompt("CV={{cv}} PROJECT={{project}}", "My CV", project_payload())

    assert "CV=My CV" in prompt
    assert '"title": "API Project"' in prompt


def test_load_json_object_accepts_markdown_wrapped_json() -> None:
    payload = load_json_object('```json\n{"profile_match_score": 80}\n```')

    assert payload == {"profile_match_score": 80}


def test_parse_project_evaluation_validates_scores_and_recommendation() -> None:
    evaluation = parse_project_evaluation(json.dumps(ai_payload()), project_payload())

    assert evaluation.profile_match_score == 80
    assert evaluation.execution_confidence_score == 70
    assert evaluation.recommendation == "apply"
    assert evaluation.cv_matches == ("Python",)


def test_parse_project_evaluation_rejects_invalid_recommendation() -> None:
    payload = ai_payload(recommendation="yes")

    with pytest.raises(ValueError, match="expected apply, maybe, or skip"):
        parse_project_evaluation(json.dumps(payload), project_payload())


def test_should_notify_requires_score_apply_and_new_url() -> None:
    evaluation = parse_project_evaluation(json.dumps(ai_payload()), project_payload())

    assert should_notify(evaluation, 75, set())
    assert not should_notify(evaluation, 85, set())
    assert not should_notify(evaluation, 75, {evaluation.project_url})


def test_should_notify_rejects_non_apply_recommendation() -> None:
    evaluation = parse_project_evaluation(
        json.dumps(ai_payload(recommendation="maybe")), project_payload()
    )

    assert not should_notify(evaluation, 75, set())


def test_notification_message_includes_both_scores() -> None:
    evaluation = parse_project_evaluation(json.dumps(ai_payload()), project_payload())

    message = notification_message(evaluation)

    assert "OpenFreela match: 80%" in message
    assert "Execution confidence: 70%" in message
    assert "Recommendation: apply" in message


def test_evaluate_project_file_saves_evaluations_and_notifies(tmp_path: Path) -> None:
    paths = write_evaluation_inputs(tmp_path)
    judge = FakeJudge(json.dumps(ai_payload()))
    notifier = FakeNotifier()

    evaluations = evaluate_project_file(paths, judge, notifier)

    assert len(evaluations) == 1
    assert "My CV" in judge.prompts[0]
    assert len(notifier.messages) == 1
    assert json.loads(paths.output_path.read_text())[0]["profile_match_score"] == 80
    assert json.loads(paths.notified_path.read_text()) == [
        "https://example.com/project"
    ]


def test_evaluate_project_file_skips_duplicate_notification(tmp_path: Path) -> None:
    paths = write_evaluation_inputs(tmp_path)
    paths.notified_path.write_text('["https://example.com/project"]')
    notifier = FakeNotifier()

    evaluate_project_file(paths, FakeJudge(json.dumps(ai_payload())), notifier)

    assert notifier.messages == []


def write_evaluation_inputs(tmp_path: Path) -> EvaluationRunConfig:
    """Write test input files and return an evaluator config.

    Example:
        config = write_evaluation_inputs(tmp_path)
    """
    projects_path = tmp_path / "projects.json"
    cv_path = tmp_path / "cv.md"
    prompt_path = tmp_path / "prompt.md"
    output_path = tmp_path / "evaluations.json"
    notified_path = tmp_path / "notified.json"
    projects_path.write_text(json.dumps([project_payload()]))
    cv_path.write_text("My CV")
    prompt_path.write_text("CV {{cv}} Project {{project}}")
    return EvaluationRunConfig(
        projects_path, cv_path, prompt_path, output_path, notified_path, 75
    )


def test_project_evaluation_to_dict_serializes_lists() -> None:
    evaluation = ProjectEvaluation(
        "url", "Title", 90, 80, "apply", "s", "w", ("a",), (), (), (), "p"
    )

    assert evaluation.to_dict()["cv_matches"] == ["a"]
