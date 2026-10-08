"""End-to-end: run the real tool (real HTTP, no mocks) against a local site with planted bugs.

Every problem planted in tests/fixtures/site is marked with a "PLANTED:" comment. This test
proves the whole pipeline - crawl, robots.txt, link checking, analyzers, scoring, CLI - finds
exactly those problems and nothing else.
"""

import json
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from sitepulse.auditor import run_audit
from sitepulse.cli import ExitCode, app
from sitepulse.config import AuditConfig
from sitepulse.models import AuditReport

pytestmark = pytest.mark.integration

SITE_DIR = Path(__file__).parents[1] / "fixtures" / "site"

PLANTED_RULES = {
    "links.internal.broken",  # /missing.html
    "links.resource.broken",  # /images/missing.png
    "links.internal.redirect",  # /blog -> /blog/
    "seo.description.missing",  # about.html (+ its copy)
    "seo.h1.missing",  # about.html (+ its copy)
    "seo.img.alt_missing",  # about.html (+ its copy)
    "seo.duplicate.content",  # copy-of-about.html == about.html
    "seo.duplicate.title",  # blog/post-1.html and post-2.html
    "seo.noindex",  # draft.html
    "seo.canonical.missing",  # about.html (+ its copy) have no canonical
    # /blog/ is served without security headers and with X-Powered-By (see FixtureHandler)
    "security.csp.missing",
    "security.clickjacking.missing",
    "security.nosniff.missing",
    "security.referrer_policy.missing",
    "security.server_disclosure",
}
# Not planted, but true: Python's http.server never compresses, and index.html is > 1 KB.
ENVIRONMENT_RULES = {"perf.compression.missing"}
EXPECTED_RULES = PLANTED_RULES | ENVIRONMENT_RULES


# What a well-configured server sends. HSTS is left out on purpose: it is only valid over
# HTTPS, and this test server speaks plain HTTP on localhost (exempt from the HTTPS rule).
SECURE_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class FixtureHandler(SimpleHTTPRequestHandler):
    server_version = "FixtureServer"  # no version number, so not a disclosure
    sys_version = ""

    def end_headers(self) -> None:
        if self.path.startswith("/blog/"):
            # PLANTED: the blog section was deployed without the security headers, by a
            # server that also advertises its PHP version.
            self.send_header("X-Powered-By", "PHP/8.1.2")
        else:
            for name, value in SECURE_HEADERS.items():
                self.send_header(name, value)
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass  # keep test output clean


@pytest.fixture(scope="module")
def site_url() -> Iterator[str]:
    """Serve the fixture site on a free port for the duration of this module."""
    handler = partial(FixtureHandler, directory=str(SITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)  # port 0 = pick any free port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def report(site_url: str) -> AuditReport:
    import asyncio

    config = AuditConfig(start_url=site_url, check_external=False, concurrency=4)
    return asyncio.run(run_audit(config))


def test_crawls_every_public_page(report: AuditReport, site_url: str) -> None:
    crawled = {page.url.removeprefix(site_url.rstrip("/")) for page in report.pages}
    assert crawled == {
        "/",
        "/about.html",
        "/blog",
        "/missing.html",
        "/draft.html",
        "/copy-of-about.html",
        "/blog/post-1.html",
        "/blog/post-2.html",
        "/index.html",
    }


def test_robots_txt_is_respected(report: AuditReport) -> None:
    assert not any("/private/" in page.url for page in report.pages)
    assert not any("/private/" in link.url for link in report.links)
    assert any("skipped because of robots.txt" in note for note in report.notes)


def test_finds_exactly_the_planted_problems(report: AuditReport) -> None:
    found = {issue.rule_id for issue in report.issues}
    assert found == EXPECTED_RULES, (
        f"missed: {EXPECTED_RULES - found}, unexpected: {found - EXPECTED_RULES}"
    )


def test_issues_point_at_the_right_urls(report: AuditReport) -> None:
    def urls(rule_id: str) -> set[str]:
        return {i.url or "" for i in report.issues if i.rule_id == rule_id}

    assert {u.rsplit("/", 1)[-1] for u in urls("links.internal.broken")} == {"missing.html"}
    assert {u.rsplit("/", 1)[-1] for u in urls("links.resource.broken")} == {"missing.png"}
    assert {u.rsplit("/", 1)[-1] for u in urls("seo.noindex")} == {"draft.html"}


def test_canonical_handles_the_index_html_alias(report: AuditReport) -> None:
    # "/" and "/index.html" are identical, but both declare canonical "/": not a duplicate.
    duplicates = [i for i in report.issues if i.rule_id == "seo.duplicate.content"]
    assert len(duplicates) == 1
    assert "index.html" not in duplicates[0].message


def test_scores_reflect_the_problems(report: AuditReport) -> None:
    scores = {s.category.value: s.score for s in report.scores}
    assert scores["links"] < 80  # a broken page link and a broken image
    assert scores["seo"] < 80
    assert scores["performance"] > 85  # fast local server; only compression is missing
    assert all(page.server_ms is not None and page.server_ms < 500 for page in report.pages)
    assert report.recommendations[0].severity.value == "critical"


def test_cli_end_to_end(site_url: str, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "report.json"
    args = ["scan", site_url, "--no-external", "--json", str(out), "--fail-under", "95"]
    result = runner.invoke(app, args)

    assert result.exit_code == ExitCode.SCORE_BELOW_THRESHOLD, result.output
    assert "SitePulse audit report" in result.output
    assert "Score" in result.output and "below --fail-under 95" in result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["overall_score"] < 95
    assert {r["rule_id"] for r in data["recommendations"]} == EXPECTED_RULES


def test_security_issues_only_on_the_misconfigured_section(report: AuditReport) -> None:
    security = [i for i in report.issues if i.category.value == "security"]
    assert security
    for issue in security:
        assert issue.affected == 3, issue.message  # /blog/, post-1.html, post-2.html
        assert "/blog/" in (issue.url or "")
        assert "3 of 8 pages" in issue.message
    disclosure = next(i for i in security if i.rule_id == "security.server_disclosure")
    assert "X-Powered-By: PHP/8.1.2" in disclosure.message
