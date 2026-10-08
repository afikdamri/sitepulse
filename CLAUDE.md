# SitePulse — Claude Code project guide

Async Python CLI that crawls a website and audits broken links, SEO tags and server response
times, then prints a scored report (0-100, A-F) with fix recommendations.

## Commands
- Install / sync deps: `uv sync`
- Run the tool: `uv run sitepulse scan <url>`
- Tests: `uv run pytest` (coverage: `uv run pytest --cov`)
- Lint + format: `uv run ruff check --fix . && uv run ruff format .`
- Type check: `uv run mypy`

Run tests, ruff and mypy before declaring any task done.

## Architecture (pipeline)
`cli.py` -> `auditor.py` (orchestrator) -> `crawler.py` (async BFS, returns `PageResult`s)
-> `link_checker.py` (HEAD/GET every link & resource, returns `LinkResult`s)
-> `analyzers/*` (each implements the `Analyzer` protocol in `analyzers/base.py`, returns `Issue`s)
-> `scoring.py` (category scores + grade) -> `reporters/*` (Rich terminal, JSON).

Rules:
- Data collection, analysis and presentation stay separate. Only `crawler.py`,
  `link_checker.py` and `robots.py` touch the network. Analyzers are pure functions of
  `AuditData`; reporters never compute scores. The auditor never prints (UI gets
  `AuditProgress` callbacks).
- Every `Issue` has a stable dotted `rule_id` (`links.internal.broken`), a severity and a
  concrete recommendation.
- All shared data types live in `models.py` (Pydantic v2). Tunable thresholds live in `config.py`.
- Inject `httpx.AsyncClient` instead of creating it inside functions, so tests can mock it with `respx`.
- New analyzer = new file in `analyzers/` + register it in `auditor.py` + unit test.
- The crawler is a worker pool over an `asyncio.Queue`; `_seen` (discovery order) is both the
  visited set and the `max_pages` budget. Never add URLs to it that won't actually be fetched.
- `urllib.robotparser` ignores non-integer `Crawl-delay` values.

## Testing
- Shared fixtures in `tests/conftest.py`: `mock_site` (respx router), `client`, `html` (page builder).
- After crawler changes, also smoke-test on a real site:
  `uv run sitepulse scan https://books.toscrape.com --max-pages 20 --depth 2`

## Conventions
- Python 3.12, full type hints, `mypy --strict` must pass.
- src layout: code in `src/sitepulse/`, tests in `tests/` mirroring module names.
- Tests never touch the real network (use `respx` or the local fixture site in `tests/fixtures/`).
- Code, comments, README: English. `LEARNING.md` is the author's learning journal: Hebrew
  explanations with technical terms in English — update it at the end of every stage.
