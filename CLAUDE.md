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

On Windows here, uv isn't on PATH: prefix commands with `py -m` (`py -m uv run pytest`).

## Claude Code setup (`.claude/`)
- `settings.json`: allow-list for routine dev commands, deny force-push / hard reset, and a
  PostToolUse hook (`hooks/format-python.sh`) that runs `ruff format` + `ruff check --fix` on
  every Python file Claude edits; unfixable lint errors come back as hook feedback (exit 2).
- `skills/add-analyzer/`: `/add-analyzer <what to detect>` - the end-to-end checklist for adding
  a new rule family. Use it for any new check.
- Work on a branch and open a PR (`gh pr create`); CI must pass before merging to `main`.

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
- Every `Issue` has a stable dotted `rule_id` (`links.internal.broken`), a severity, a
  concrete recommendation, and `affected` (pages it touches; site-wide issues set it).
  New rule ids need a title in `rules.py` (enforced by `tests/test_rules.py`).
- Scoring (`scoring.py`) is per rule, not per issue: severity weight x prevalence. The formula
  is documented in its module docstring; keep tests with hand-computed values in sync.
- All shared data types live in `models.py` (Pydantic v2). Tunable thresholds live in `config.py`.
- Inject `httpx.AsyncClient` instead of creating it inside functions, so tests can mock it with `respx`.
- New analyzer = new file in `analyzers/` + register it in `auditor.py` + unit test.
- The crawler is a worker pool over an `asyncio.Queue`; `_seen` (discovery order) is both the
  visited set and the `max_pages` budget. Never add URLs to it that won't actually be fetched.
- `urllib.robotparser` ignores non-integer `Crawl-delay` values.
- Analyzers that read HTML split extraction (HTML -> plain facts dataclass) from rules
  (facts -> Issues), like `extract_seo_facts` / `SeoAnalyzer`.
- Performance rules use `PageResult.server_ms` (TTFB minus TCP/TLS setup measured by
  `ConnectionTimer` via httpx trace events), never raw TTFB: our own concurrency opens fresh
  connections, which must not be blamed on the server.
- httpx is installed with `[brotli,zstd]` so `Accept-Encoding` matches real browsers; some
  servers only compress with Brotli.
- Timing code uses `time.perf_counter()` (Windows `monotonic()` ticks every ~15.6 ms).
- `cli.py` has no display code: `reporters/terminal.py` (Rich, takes an injected `Console`)
  and `reporters/json_report.py`. Progress bars and errors go to stderr; stdout carries only
  the report, so `--json -` emits pure JSON. Empty report sections are skipped.
- Reporter tests render into `Console(file=io.StringIO(), width=140, color_system=None)`.
  After changing layout, also look at a real run - tests can't see spacing problems.
- Output must survive non-UTF-8 streams (the author's Windows uses cp1255) (Windows NUL, legacy consoles): `make_streams_safe`
  in `cli.py`. Verify with `uv run sitepulse scan <url> > /dev/null; echo $?`.

## Testing
- Shared fixtures in `tests/conftest.py`: `mock_site` (respx router), `client`, `html` (page builder).
- Analyzer tests use a baseline: a perfect page must yield zero issues, and each test breaks
  exactly one thing and asserts exactly one rule fires (`tests/analyzers/test_seo.py`).
- `tests/integration/` serves `tests/fixtures/site/` (problems marked `PLANTED:` in the HTML)
  with a real `http.server` and asserts the exact set of rule ids found. New rule = plant it in
  the fixture site and add it to `PLANTED_RULES`.
- CI (`.github/workflows/ci.yml`) runs ruff, mypy and pytest (coverage >= 90%) on
  Linux + Windows, Python 3.12 + 3.13. Run the same commands locally before pushing.
- Regenerate the README screenshot with `uv run python scripts/screenshot.py`.
- After crawler changes, also smoke-test on a real site:
  `uv run sitepulse scan https://books.toscrape.com --max-pages 20 --depth 2`

## Conventions
- Python 3.12, full type hints, `mypy --strict` must pass.
- src layout: code in `src/sitepulse/`, tests in `tests/` mirroring module names.
- Tests never touch the real network (use `respx` or the local fixture site in `tests/fixtures/`).
- Code, comments, README: English. `LEARNING.md` is the author's private learning journal
  (gitignored, local only): Hebrew explanations with technical terms in English — update it
  at the end of every stage when it exists.
