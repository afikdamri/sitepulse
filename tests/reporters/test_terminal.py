import io
import json
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from sitepulse import __version__
from sitepulse.analyzers import compute_performance_stats
from sitepulse.models import AuditReport, Category, Issue, LinkResult, PageResult, Severity
from sitepulse.reporters import TerminalReporter, report_to_json, write_json
from sitepulse.scoring import score_issues

SITE = "https://example.com"


def make_report(
    issues: list[Issue] | None = None, links: list[LinkResult] | None = None
) -> AuditReport:
    issues = issues or []
    pages = [
        PageResult(
            url=f"{SITE}/{name}",
            depth=0,
            status_code=200,
            content_type="text/html",
            content_encoding="gzip",
            ttfb_ms=ttfb,
            response_time_ms=ttfb + 30,
            size_bytes=40_960,
            transfer_bytes=8_192,
        )
        for name, ttfb in (("", 120), ("slow", 900), ("about", 150))
    ]
    scored = score_issues(issues, total_pages=len(pages))
    return AuditReport(
        target_url=f"{SITE}/",
        started_at=datetime(2026, 10, 8, 12, 30, tzinfo=UTC),
        duration_s=3.2,
        pages=pages,
        links=links or [],
        issues=issues,
        performance=compute_performance_stats(pages),
        scores=scored.scores,
        overall_score=scored.overall,
        recommendations=scored.recommendations,
        notes=["2 URL(s) skipped because of robots.txt"],
    )


def issue(rule_id: str, severity: Severity, category: Category, n: int = 0) -> Issue:
    return Issue(
        rule_id=rule_id,
        category=category,
        severity=severity,
        message=f"{rule_id} problem #{n}",
        recommendation=f"Fix {rule_id}",
        url=f"{SITE}/page{n}",
    )


def render(report: AuditReport, console: Console | None = None, **options: object) -> str:
    buffer = io.StringIO()
    console = console or Console(file=buffer, width=140, color_system=None)
    TerminalReporter(console, **options).render(report)  # type: ignore[arg-type]
    return buffer.getvalue()


def test_perfect_report() -> None:
    text = render(make_report())
    assert "SitePulse audit report" in text
    assert f"{SITE}/" in text
    assert "3 pages crawled" in text
    assert "100/100  A" in text
    assert "no critical issues" in text
    assert "No issues found" in text
    assert "All checks passed" in text
    assert "Broken links" not in text  # empty sections are skipped


def test_scorecards_and_recommendations() -> None:
    issues = [
        issue("links.internal.broken", Severity.CRITICAL, Category.LINKS),
        issue("seo.h1.missing", Severity.WARNING, Category.SEO),
    ]
    text = render(make_report(issues))
    assert "1 critical issue(s)" in text
    assert "1 critical" in text and "1 warning" in text  # per-category counts
    assert "Top 2 recommendations" in text
    assert "Broken internal links" in text  # human title from rules.py
    assert "Fix links.internal.broken" in text
    assert "e.g. /page0" in text
    assert text.index("Broken internal links") < text.index("Missing <h1> headings")  # by impact
    assert "1 critical issue(s) need attention" in text


def test_top_limits_recommendations() -> None:
    issues = [issue(f"seo.rule{i}", Severity.INFO, Category.SEO) for i in range(5)]
    text = render(make_report(issues), top=2)
    assert "Top 2 recommendations" in text
    assert "+3 more - run with --details" in text


def test_broken_links_table_hides_bot_blocked_external_links() -> None:
    links = [
        LinkResult(
            url=f"{SITE}/gone",
            is_internal=True,
            status_code=404,
            found_on=[f"{SITE}/", f"{SITE}/about"],
        ),
        LinkResult(url="https://dead.example/", is_internal=False, error="timeout"),
        LinkResult(url="https://linkedin.com/x", is_internal=False, status_code=999),
        LinkResult(url=f"{SITE}/ok", is_internal=True, status_code=200),
    ]
    text = render(make_report(links=links))
    assert "Broken links (2)" in text
    assert f"{SITE}/gone" in text
    assert "/ (+1)" in text  # found on 2 pages
    assert "timeout" in text
    assert "linkedin" not in text  # 999 = bot protection, not a broken link


def test_performance_section() -> None:
    text = render(make_report())
    assert "Performance (3 pages measured)" in text
    assert "Server response" in text
    assert "120 KB → 24 KB transferred" in text
    assert "3/3 pages compressed (80% saved)" in text
    slowest = text[text.index("Slowest pages") :]
    assert slowest.index(f"{SITE}/slow") < slowest.index(f"{SITE}/about")


def test_details_lists_every_issue_and_page() -> None:
    issues = [issue("seo.h1.missing", Severity.WARNING, Category.SEO, n) for n in range(3)]
    brief = render(make_report(issues))
    full = render(make_report(issues), details=True)
    assert "seo.h1.missing problem #2" not in brief
    assert "seo.h1.missing problem #2" in full
    assert "Crawled pages (3)" in full


def test_notes_are_shown() -> None:
    assert "2 URL(s) skipped because of robots.txt" in render(make_report())


def test_ascii_fallback_for_legacy_consoles() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", errors="replace")
    console = Console(file=stream, width=140, color_system=None)
    TerminalReporter(console).render(make_report())
    stream.flush()
    text = raw.getvalue().decode("cp1252")
    assert "#" * 20 in text  # score bar drawn with ASCII
    assert "█" not in text and "?" * 20 not in text  # no mangled Unicode
    assert "->" in text


def test_json_report(tmp_path: Path) -> None:
    report = make_report([issue("seo.h1.missing", Severity.WARNING, Category.SEO)])
    path = tmp_path / "report.json"
    write_json(report, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == json.loads(report_to_json(report))
    assert data["tool_version"] == __version__
    assert data["recommendations"][0]["rule_id"] == "seo.h1.missing"
    assert "html" not in data["pages"][0]
