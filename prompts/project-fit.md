You are evaluating whether I should apply to a freelance project.

Your job is NOT to simply compare keywords between my CV and the project description.

Perform two separate evaluations:

## Profile Match
- How closely the project aligns with my documented experience, technologies, domains, and past work.
- This is a CV-based assessment only.

## Execution Capability
- Estimate whether I can successfully deliver the project based on my overall seniority, engineering maturity, problem-solving ability, transferable skills, and likely ability to learn missing pieces.
- Do not require direct evidence in the CV for every task.
- Senior professionals can often execute projects outside their exact previous stack or domain.
- Infer the required seniority from the project description and compare it against my apparent seniority.
- If the project mainly requires skills that an experienced engineer could reasonably learn or adapt to quickly, increase execution confidence even when CV overlap is low.

## Important considerations:

- Clients are often non-technical and may describe solutions incorrectly.
- Focus on the underlying problem being solved, not only on the listed technologies.
- Distinguish between domain knowledge gaps and implementation gaps.
- Missing tools, frameworks, or APIs are usually less important than lacking the required engineering level.
- A project may have low CV match but still be a strong application opportunity.
- Do not penalize heavily for missing technologies when the required competence is transferable.
- Give significant weight to seniority fit, architecture complexity, scope complexity, ambiguity handling, and delivery ownership.
- Assume that experienced engineers can learn reasonable new technologies during execution.
- Only recommend "skip" when there is a substantial risk that I cannot realistically deliver the project or when the project requires highly specialized expertise that is clearly absent.

Return only valid JSON. Do not include Markdown, comments, or extra text.

Required JSON shape:

{
  "profile_match_score": 0,
  "execution_confidence_score": 0,
  "recommendation": "apply | maybe | skip",
  "summary": "Short explanation of the overall fit.",
  "why_apply": "Why I should apply if the recommendation is apply; otherwise explain the main decision.",
  "cv_matches": ["Skills or experiences from my CV that match the project."],
  "adjacent_skills": ["Relevant skills I can probably transfer or learn quickly."],
  "missing_skills": ["Important gaps or unknowns."],
  "risks": ["Delivery risks, ambiguity, scope problems, or red flags."],
  "proposal_angle": "How I should position my proposal if I apply."
}

Scoring rules:

- `profile_match_score` is how much the project matches my CV, from 0 to 100.
- `execution_confidence_score` is how likely I can execute it successfully, from 0 to 100, including adjacent skills and learnable gaps.
- `recommendation` must be exactly one of: `apply`, `maybe`, `skip`.
- Recommend `apply` only when the project is a strong practical opportunity.

CV:

{{cv}}

Project:

{{project}}
