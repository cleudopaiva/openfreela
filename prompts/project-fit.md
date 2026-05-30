You are evaluating whether I should apply to a freelance project.

Use my CV to estimate how much the project matches my documented profile.
Also estimate whether I can execute the project, including adjacent skills or tasks I can reasonably learn even if they are not explicit in my CV.

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
