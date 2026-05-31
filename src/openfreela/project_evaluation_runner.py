from __future__ import annotations

from openfreela.project_evaluator import (
    EvaluationRunConfig,
    ProjectEvaluation,
    ProjectJudge,
    ProjectNotifier,
    load_evaluations,
    load_notified_urls,
    load_project_objects,
    notification_message,
    parse_project_evaluation,
    read_required_text,
    render_prompt,
    save_evaluations,
    save_notified_urls,
    should_notify,
)


def run_project_evaluation_file(
    config: EvaluationRunConfig,
    judge: ProjectJudge,
    notifier: ProjectNotifier,
) -> list[ProjectEvaluation]:
    """Evaluate scraped projects incrementally and return saved evaluations.

    Example:
        evaluations = run_project_evaluation_file(config, judge, notifier)
    """
    projects = load_project_objects(config.projects_path)
    cv = read_required_text(config.cv_path)
    template = read_required_text(config.prompt_path)
    notified_urls = load_notified_urls(config.notified_path)
    evaluations = load_evaluations(config.output_path)
    log_evaluation_start(projects, evaluations)
    evaluate_project_incrementally(
        projects, cv, template, judge, notifier, config, evaluations, notified_urls
    )
    save_notified_urls(config.notified_path, notified_urls)
    return evaluations


def log_evaluation_start(
    projects: list[dict[str, object]], evaluations: list[ProjectEvaluation]
) -> None:
    """Log the starting state for an evaluation run.

    Example:
        log_evaluation_start(projects, evaluations)
    """
    print(f"Loaded {len(projects)} projects.")
    print(f"Loaded {len(evaluations)} previous evaluations.")


def evaluate_project_incrementally(
    projects: list[dict[str, object]],
    cv: str,
    template: str,
    judge: ProjectJudge,
    notifier: ProjectNotifier,
    config: EvaluationRunConfig,
    evaluations: list[ProjectEvaluation],
    notified_urls: set[str],
) -> None:
    """Evaluate projects one by one and persist each successful result.

    Example:
        evaluate_project_incrementally(
            projects, cv, template, judge, notifier, config, [], set()
        )
    """
    evaluated_urls = {evaluation.project_url for evaluation in evaluations}
    for index, project in enumerate(projects, start=1):
        evaluate_project_step(
            index,
            len(projects),
            project,
            cv,
            template,
            judge,
            notifier,
            config,
            evaluations,
            evaluated_urls,
            notified_urls,
        )


def evaluate_project_step(
    index: int,
    total: int,
    project: dict[str, object],
    cv: str,
    template: str,
    judge: ProjectJudge,
    notifier: ProjectNotifier,
    config: EvaluationRunConfig,
    evaluations: list[ProjectEvaluation],
    evaluated_urls: set[str],
    notified_urls: set[str],
) -> None:
    """Evaluate one project and persist success while logging failures.

    Example:
        evaluate_project_step(
            1, 10, project, cv, template, judge, notifier, config, [], set(), set()
        )
    """
    title = project_title(project)
    if exceeds_max_proposals(project, config.max_proposals):
        print(proposal_skip_message(index, total, title, project, config.max_proposals))
        return
    if project_already_evaluated(project, evaluated_urls):
        print(f"Skipping {index}/{total}: {title} (already evaluated)")
        return
    print(f"Evaluating {index}/{total}: {title}")
    try:
        evaluation = evaluate_one_project(project, cv, template, judge)
    except Exception as error:
        print(f"Failed {index}/{total}: {title}: {error}")
        return
    persist_successful_evaluation(evaluation, config, evaluations, evaluated_urls)
    notify_successful_evaluation(evaluation, config, notified_urls, notifier)


def evaluate_one_project(
    project: dict[str, object], cv: str, template: str, judge: ProjectJudge
) -> ProjectEvaluation:
    """Evaluate one project with the AI judge.

    Example:
        evaluation = evaluate_one_project(project, cv, template, judge)
    """
    prompt = render_prompt(template, cv, project)
    return parse_project_evaluation(judge.chat_json(prompt), project)


def persist_successful_evaluation(
    evaluation: ProjectEvaluation,
    config: EvaluationRunConfig,
    evaluations: list[ProjectEvaluation],
    evaluated_urls: set[str],
) -> None:
    """Persist one successful real evaluation immediately.

    Example:
        persist_successful_evaluation(evaluation, config, evaluations, set())
    """
    evaluations.append(evaluation)
    evaluated_urls.add(evaluation.project_url)
    save_evaluations(config.output_path, evaluations)
    print(evaluation_saved_message(evaluation))


def notify_successful_evaluation(
    evaluation: ProjectEvaluation,
    config: EvaluationRunConfig,
    notified_urls: set[str],
    notifier: ProjectNotifier,
) -> None:
    """Notify for one matching evaluation and persist notification state.

    Example:
        notify_successful_evaluation(evaluation, config, set(), notifier)
    """
    if not should_notify(evaluation, notified_urls):
        return
    try:
        notifier.send_message(notification_message(evaluation))
    except Exception as error:
        print(f"Failed Telegram notification for {evaluation.title}: {error}")
        return
    notified_urls.add(evaluation.project_url)
    save_notified_urls(config.notified_path, notified_urls)
    print("Sent Telegram notification.")


def evaluation_saved_message(evaluation: ProjectEvaluation) -> str:
    """Return a concise progress message for one saved evaluation.

    Example:
        message = evaluation_saved_message(evaluation)
    """
    return (
        "Saved evaluation: "
        f"{evaluation.profile_match_score}% match, "
        f"{evaluation.execution_confidence_score}% execution, "
        f"recommendation={evaluation.recommendation}"
    )


def project_already_evaluated(
    project: dict[str, object], evaluated_urls: set[str]
) -> bool:
    """Return whether a project URL already has a saved evaluation.

    Example:
        ok = project_already_evaluated(project, {"url"})
    """
    value = project.get("project_url")
    return isinstance(value, str) and value in evaluated_urls


def exceeds_max_proposals(
    project: dict[str, object], max_proposals: int | None
) -> bool:
    """Return whether a project should be skipped due to too many proposals.

    Example:
        skip = exceeds_max_proposals({"proposals": 31}, 30)
    """
    if max_proposals is None:
        return False
    proposals = project.get("proposals")
    return (
        isinstance(proposals, int)
        and not isinstance(proposals, bool)
        and proposals > max_proposals
    )


def proposal_skip_message(
    index: int,
    total: int,
    title: str,
    project: dict[str, object],
    max_proposals: int | None,
) -> str:
    """Return a progress message for a proposal-count skip.

    Example:
        message = proposal_skip_message(1, 2, "API", {"proposals": 31}, 30)
    """
    proposals = project.get("proposals")
    return (
        f"Skipping {index}/{total}: {title} "
        f"(proposals={proposals} > max_proposals={max_proposals})"
    )


def project_title(project: dict[str, object]) -> str:
    """Return a readable project title for logs.

    Example:
        title = project_title({"title": "API"})
    """
    value = project.get("title")
    return value if isinstance(value, str) and value else "(untitled project)"
