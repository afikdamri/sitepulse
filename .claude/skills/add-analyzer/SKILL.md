---
name: add-analyzer
description: Add a new analyzer (a new family of audit rules) to SitePulse end to end - data collection, rules, scoring, report, fixture site and tests. Use when the user asks to check something new about a website (e.g. "detect missing security headers", "flag thin content", "check structured data").
argument-hint: "<what the analyzer should detect>"
---

# Add a SitePulse analyzer

You are adding a new analyzer for: **$ARGUMENTS**

Work through the checklist in order. Each step names the file to change and the existing code to
copy the pattern from. Read the referenced file before editing it.

## 1. Design first (no code yet)

Write down, and confirm with the user if anything is ambiguous:
- **Rules**: for each, a stable dotted `rule_id` (`<category>.<thing>.<problem>`), a severity
  (`critical` = broken for users, `warning` = real problem, `info` = nice to have) and a one-line
  recommendation. Severity must be defensible - avoid false positives (see the `alt=""`,
  SVG `<title>` and bot-blocked-link decisions in `LEARNING.md`).
- **Category**: an existing one (`links`, `seo`, `performance`) or a new one.
- **Data needed**: is everything already in `PageResult` / `LinkResult`? If not, what raw fact
  must the crawler collect?

## 2. Collect raw data (only if needed)

- Add the field to `PageResult` in `src/sitepulse/models.py` - facts only, never judgements.
  Large fields get `exclude=True`, like `html`.
- Populate it in `Crawler._fetch` (`src/sitepulse/crawler.py`). Only the crawler, link checker
  and robots module may touch the network.
- Test it in `tests/test_crawler.py` with a `mock_site` route.

## 3. Write the analyzer

- New file `src/sitepulse/analyzers/<name>.py`. Copy the structure of `analyzers/seo.py`:
  - an extraction function (raw data -> plain facts dataclass) if parsing is involved;
  - a class with `category` and `analyze(self, data: AuditData) -> list[Issue]`;
  - an `_issue(...)` helper; set `affected=` for site-wide issues (pages the problem touches).
- Pure function of `AuditData`: no network, no printing, no scoring.
- Thresholds that are judgement calls go in `src/sitepulse/config.py`, not in the analyzer.
- Export it from `analyzers/__init__.py` and add it to `default_analyzers()` in `auditor.py`.
- Add a human title for every rule id in `src/sitepulse/rules.py`.

## 4. New category only

- Add it to `Category` in `models.py`.
- Add a weight to `CATEGORY_WEIGHTS` in `scoring.py` and rebalance so weights sum to 1.0.
  Explain the new weights in the module docstring and README "How scoring works".
- Add a label to `CATEGORY_LABELS` in `reporters/terminal.py`.
- Update tests with hand-computed values that depend on the weights (`tests/test_scoring.py`,
  `tests/reporters/test_terminal.py`).

## 5. Tests

- `tests/analyzers/test_<name>.py` with the **baseline pattern**: a perfect input yields zero
  issues; each other test breaks exactly one thing and asserts exactly one rule fires, with its
  severity and URL. See `tests/analyzers/test_seo.py`.
- Plant each new problem in the fixture site `tests/fixtures/site/` (mark it with a
  `PLANTED:` comment) and add the rule ids to `PLANTED_RULES` in
  `tests/integration/test_fixture_site.py`.

## 6. Verify

Run all of these; every one must pass:

```bash
py -m uv run ruff check . && py -m uv run ruff format --check .
py -m uv run mypy
py -m uv run pytest --cov --cov-fail-under=90
py -m uv run sitepulse scan https://books.toscrape.com --max-pages 10
```

Look at the real report: do the new findings make sense? Verify any surprising result against
the raw source (e.g. `curl -sI <url>` for headers) before trusting it.

## 7. Document

- README: feature list and rule count.
- `LEARNING.md`: concepts, decisions, bugs found (Hebrew prose, English terms).
- `CLAUDE.md`: only if a new convention was introduced.
