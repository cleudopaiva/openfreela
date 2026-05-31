# OpenFreela

OpenFreela helps collect freelance project listings from 99freelas, evaluate them with a local AI model, and notify you about the best opportunities.

The current implementation focuses on 99freelas projects in the software development category. It opens a real Chromium browser through SeleniumBase CDP mode, lets you log in manually when needed, and then uses Playwright over CDP to scrape project data into a local JSON file.

## What It Does

- Opens the 99freelas login page for manual authentication.
- Saves the authenticated browser session locally.
- Reuses that session for future scraping runs.
- Scrapes software, web, mobile, and development projects from 99freelas.
- Follows pagination automatically until the last page.
- Saves structured project data as JSON.
- Captures expanded project descriptions from the page HTML, including content hidden behind `Expandir`.
- Evaluates each project against a Markdown CV using Ollama and Qwen.
- Sends Telegram notifications for strong `apply` recommendations.

## Requirements

- Python `3.14`.
- `uv` for dependency management.
- A local browser environment that can open Chromium.

Install dependencies:

```bash
uv sync --dev
```

If Playwright browsers are not installed yet, run:

```bash
uv run playwright install chromium
```

## Login Flow

99freelas may show captcha during login. OpenFreela does not try to bypass captcha automatically. You log in manually in the browser window.

Run:

```bash
uv run openfreela login-99freelas
```

Then:

1. Complete login manually in the opened browser.
2. Solve captcha manually if it appears.
3. Return to the terminal.
4. Press Enter to save the session.

The session is saved to:

```text
.auth/99freelas.json
```

This file is ignored by Git because it contains local authentication state.

If the session expires, run `login-99freelas` again.

## Scraping Projects

Run:

```bash
uv run openfreela scrape-99freelas
```

The scraper uses this 99freelas category page:

```text
https://www.99freelas.com.br/projects?categoria=web-mobile-e-software
```

It detects the last page from the pagination button named `Última`, using its `data-page` value, then visits every page using the `page` query parameter.

Example page URL:

```text
https://www.99freelas.com.br/projects?categoria=web-mobile-e-software&page=2
```

The output is saved to:

```text
data/99freelas-projects.json
```

The `data/` directory is ignored by Git because it contains local scrape results.

## Headless Mode

By default, scraping opens a visible browser because it is more reliable for authenticated pages and anti-bot checks.

To run in headless mode:

```bash
uv run openfreela scrape-99freelas --headless
```

Use this only after confirming the normal headed flow works.

## AI Evaluation

After scraping projects, you can ask a local Ollama model to evaluate each project against your CV.

Create your CV file:

```text
profile/cv.md
```

This file is ignored by Git because it contains private profile information.

The prompt template is stored at:

```text
prompts/project-fit.md
```

Edit that file whenever you want to change how the AI judges projects.

Copy `.env.example` to `.env` if you prefer local configuration over shell exports. Values already exported in your shell take precedence over `.env`.

The default provider is Ollama and the default local model is:

```text
qwen3.5:latest
```

Make sure Ollama is running and the model is available:

```bash
ollama pull qwen3.5:latest
```

Set Telegram credentials:

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

Optional environment variables:

```bash
export OPENFREELA_AI_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="qwen3.5:latest"
export OPENFREELA_OLLAMA_TIMEOUT="300"
export OPENFREELA_MIN_PROFILE_MATCH="75"
```

To use OpenAI instead:

```bash
export OPENFREELA_AI_PROVIDER="openai"
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENFREELA_OPENAI_TIMEOUT="300"
```

Check the configured AI provider before evaluating real projects:

```bash
uv run openfreela test-ai --ai-provider ollama --ai-verbose
uv run openfreela test-ai --ai-provider openai
```

Evaluate scraped projects:

```bash
uv run openfreela evaluate-projects
uv run openfreela evaluate-projects --ai-provider openai
uv run openfreela evaluate-projects --ai-provider ollama --ai-verbose
```

For local Ollama debugging, write safe request metadata to JSONL:

```bash
uv run openfreela evaluate-projects --ai-provider ollama --ai-log data/ai-requests.jsonl
```

AI logs include provider, model, base URL, duration, prompt/response character counts, and Ollama timing/token metrics when available. They do not include your full CV, prompt, API token, or model response body.

The evaluator reads:

```text
data/99freelas-projects.json
profile/cv.md
prompts/project-fit.md
```

It writes:

```text
data/99freelas-project-evaluations.json
data/notified-projects.json
```

Successful evaluations are written incrementally after each project, so progress is kept if Ollama times out or one project fails to parse. Re-running the command skips project URLs already present in `data/99freelas-project-evaluations.json`.

Telegram notifications are sent only when both conditions are true:

- `profile_match_score >= 75`
- `recommendation == "apply"`

Already notified project URLs are stored in `data/notified-projects.json` so repeated runs do not spam Telegram.

## Evaluation Output

Each AI evaluation has fields like:

```json
{
  "project_url": "https://www.99freelas.com.br/project/example-123?fs=t",
  "title": "Atualização site de WIX para WordPress",
  "profile_match_score": 82,
  "execution_confidence_score": 68,
  "recommendation": "apply",
  "summary": "Strong match with web development and WordPress experience.",
  "why_apply": "The project overlaps with documented web delivery experience.",
  "cv_matches": ["WordPress", "web development"],
  "adjacent_skills": ["CRM integrations"],
  "missing_skills": ["Specific ERP tool"],
  "risks": ["Large scope"],
  "proposal_angle": "Lead with web platform and integration experience."
}
```

The two scores are intentionally separate:

- `profile_match_score`: how much the project matches your CV.
- `execution_confidence_score`: how likely you can execute it, including adjacent or learnable skills.

## Output Format

Each scraped project is saved as a JSON object with fields like:

```json
{
  "title": "Atualização site de WIX para WordPress",
  "description": "Full project description, including expanded hidden content...",
  "budget": null,
  "skills": ["Chatbot", "Wordpress"],
  "project_url": "https://www.99freelas.com.br/project/example-123?fs=t",
  "posted_at": "5 dias atrás",
  "remaining_time": "24 dias e 18 horas",
  "proposals": 63,
  "interested": 78,
  "level": "Intermediário",
  "raw_text": "Raw normalized text from the project card..."
}
```

Important fields:

- `title`: project title from the project link.
- `description`: full description from the HTML, including hidden expanded text.
- `skills`: project skill tags listed by 99freelas.
- `project_url`: absolute URL for the project page.
- `posted_at`: when the project was published.
- `remaining_time`: how much time is left to send proposals.
- `proposals`: number of proposals already submitted.
- `interested`: number of interested freelancers.
- `level`: project difficulty level, such as `Iniciante`, `Intermediário`, or `Especialista`.

## Development Checks

Run formatting, linting, type checking, tests, and dependency audit locally:

```bash
uv run ruff format --check
uv run ruff check
uv run mypy src tests
uv run pytest
uv run pip-audit
```

Tests enforce at least `85%` coverage.

## Continuous Integration

GitHub Actions runs the same quality gate on pushes and pull requests:

```text
OpenFreela Quality Gate
```

The workflow checks:

- Code formatting.
- Ruff lint rules.
- Strict mypy typing.
- Tests with coverage threshold.
- Dependency vulnerabilities with `pip-audit`.

## Current Limitations

- Only 99freelas is supported.
- Login is manual.
- Captcha solving is manual.
- AI evaluation depends on a local Ollama server.
- Telegram notifications require `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

## Intended Next Step

The next major feature is ranking and filtering the saved evaluations so the best opportunities are easier to review from the terminal or a small UI.
