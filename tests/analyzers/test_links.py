import pytest

from sitepulse.analyzers import AuditData, LinkAnalyzer
from sitepulse.analyzers.base import describe_pages
from sitepulse.config import AuditConfig
from sitepulse.models import Category, Issue, LinkResult, PageResult, Severity

SITE = "https://example.com"


def analyze(
    links: list[LinkResult] | None = None, pages: list[PageResult] | None = None
) -> list[Issue]:
    data = AuditData(config=AuditConfig(start_url=SITE), pages=pages or [], links=links or [])
    return LinkAnalyzer().analyze(data)


def link(url: str = f"{SITE}/x", **fields: object) -> LinkResult:
    defaults: dict[str, object] = {"is_internal": url.startswith(SITE), "found_on": [f"{SITE}/"]}
    return LinkResult.model_validate({"url": url, **defaults, **fields})


@pytest.mark.parametrize(
    ("fields", "rule_id", "severity"),
    [
        ({"status_code": 404}, "links.internal.broken", Severity.CRITICAL),
        ({"status_code": 500}, "links.internal.broken", Severity.CRITICAL),
        ({"status_code": 404, "is_resource": True}, "links.resource.broken", Severity.CRITICAL),
        ({"error": "timeout"}, "links.unreachable", Severity.CRITICAL),
        ({"status_code": 200, "redirect_count": 1}, "links.internal.redirect", Severity.INFO),
        ({"status_code": 200, "redirect_count": 3}, "links.redirect.chain", Severity.WARNING),
        (
            {"status_code": 200, "redirect_count": 1, "final_url": "http://example.com/x/"},
            "links.redirect.insecure",
            Severity.WARNING,
        ),
    ],
)
def test_internal_link_rules(fields: dict[str, object], rule_id: str, severity: Severity) -> None:
    [issue] = analyze([link(**fields)])
    assert issue.rule_id == rule_id
    assert issue.severity == severity
    assert issue.category == Category.LINKS
    assert issue.url == f"{SITE}/x"
    assert issue.recommendation


@pytest.mark.parametrize(
    ("fields", "rule_id", "severity"),
    [
        ({"status_code": 404}, "links.external.broken", Severity.WARNING),
        ({"status_code": 403}, "links.external.unverifiable", Severity.INFO),
        ({"status_code": 999}, "links.external.unverifiable", Severity.INFO),
        ({"error": "ConnectError: dns"}, "links.unreachable", Severity.WARNING),
        ({"status_code": 404, "is_resource": True}, "links.resource.broken", Severity.CRITICAL),
    ],
)
def test_external_link_rules(fields: dict[str, object], rule_id: str, severity: Severity) -> None:
    [issue] = analyze([link("https://other.com/x", **fields)])
    assert (issue.rule_id, issue.severity) == (rule_id, severity)


@pytest.mark.parametrize(
    "fields",
    [
        {"status_code": 200},
        {"status_code": 301},  # final status after redirects is what matters; 3xx alone is fine
        {"status_code": 200, "redirect_count": 1, "url": "https://other.com/"},  # http->https etc.
    ],
)
def test_healthy_links_produce_no_issues(fields: dict[str, object]) -> None:
    assert analyze([link(**fields)]) == []


def test_message_names_the_source_pages() -> None:
    sources = [f"{SITE}/p{i}" for i in range(5)]
    [issue] = analyze([link(status_code=404, found_on=sources)])
    assert "/p0, /p1, /p2 and 2 more" in issue.message


def test_mixed_content_on_https_page() -> None:
    pages = [
        PageResult(
            url=f"{SITE}/",
            depth=0,
            resources=["http://cdn.example.com/a.js", "https://cdn.example.com/b.css"],
        ),
        PageResult(url="http://example.com/plain", depth=0, resources=["http://x.com/a.js"]),
    ]
    [issue] = analyze(pages=pages)
    assert issue.rule_id == "links.mixed_content"
    assert issue.url == f"{SITE}/"
    assert "http://cdn.example.com/a.js" in issue.message


def test_describe_pages() -> None:
    assert describe_pages([f"{SITE}/"]) == "/"
    assert describe_pages([f"{SITE}/a?q=1", f"{SITE}/b"]) == "/a?q=1, /b"
