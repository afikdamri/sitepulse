from typing import Any

import pytest

from sitepulse.analyzers import AuditData, SecurityAnalyzer
from sitepulse.analyzers.security import extract_security_facts
from sitepulse.config import AuditConfig, SecurityThresholds
from sitepulse.models import Category, Issue, PageResult, Severity

SITE = "https://example.com"
GOOD_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "content-security-policy": "default-src 'self'",
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "server": "nginx",
}


def page(
    url: str = f"{SITE}/",
    headers: dict[str, str] | None = None,
    html: str = "<html><body>ok</body></html>",
    status: int = 200,
) -> PageResult:
    return PageResult(
        url=url,
        depth=0,
        status_code=status,
        content_type="text/html",
        headers=GOOD_HEADERS if headers is None else headers,
        html=html,
    )


def with_headers(**changes: str | None) -> dict[str, str]:
    """GOOD_HEADERS with some replaced (str) or removed (None); `_` in names becomes `-`."""
    headers = dict(GOOD_HEADERS)
    for name, value in changes.items():
        key = name.replace("_", "-")
        if value is None:
            headers.pop(key, None)
        else:
            headers[key] = value
    return headers


def analyze(pages: list[PageResult], security: SecurityThresholds | None = None) -> list[Issue]:
    config = AuditConfig(start_url=SITE, security=security or SecurityThresholds())
    return SecurityAnalyzer().analyze(AuditData(config=config, pages=pages, links=[]))


def rule_ids(issues: list[Issue]) -> list[str]:
    return sorted(issue.rule_id for issue in issues)


# ---- extraction ----------------------------------------------------------------------------


def test_extract_facts_from_a_well_configured_page() -> None:
    facts = extract_security_facts(page())
    assert facts.is_https and not facts.is_local
    assert facts.hsts_max_age == 31536000
    assert facts.has_csp and facts.frame_protected and facts.nosniff
    assert facts.has_referrer_policy
    assert facts.disclosed == []  # "nginx" without a version is fine


def test_meta_csp_counts_but_frame_ancestors_needs_a_header() -> None:
    html = '<head><meta http-equiv="Content-Security-Policy" content="default-src \'self\'">'
    facts = extract_security_facts(page(headers={}, html=html))
    assert facts.has_csp
    assert not facts.frame_protected


@pytest.mark.parametrize(
    ("url", "is_local"),
    [
        ("http://localhost:8000/", True),
        ("http://127.0.0.1/", True),
        ("http://app.localhost/", True),
        ("http://example.com/", False),
    ],
)
def test_local_dev_servers_are_recognized(url: str, is_local: bool) -> None:
    assert extract_security_facts(page(url=url)).is_local is is_local


# ---- rules ------------------------------------------------------------------------------------


def test_well_configured_site_has_no_issues() -> None:
    assert analyze([page(f"{SITE}/a"), page(f"{SITE}/b")]) == []


@pytest.mark.parametrize(
    ("header_changes", "expected_rule", "severity"),
    [
        ({"strict_transport_security": None}, "security.hsts.missing", Severity.WARNING),
        # max-age=0 actively tells browsers to forget HSTS (seen on books.toscrape.com)
        ({"strict_transport_security": "max-age=0"}, "security.hsts.missing", Severity.WARNING),
        ({"strict_transport_security": "max-age=86400"}, "security.hsts.weak", Severity.INFO),
        ({"content_security_policy": None}, "security.csp.missing", Severity.WARNING),
        ({"x_frame_options": None}, "security.clickjacking.missing", Severity.WARNING),
        (
            {"x_frame_options": "ALLOW-FROM https://x"},
            "security.clickjacking.missing",
            Severity.WARNING,
        ),
        ({"x_content_type_options": None}, "security.nosniff.missing", Severity.INFO),
        ({"referrer_policy": None}, "security.referrer_policy.missing", Severity.INFO),
        ({"server": "nginx/1.18.0"}, "security.server_disclosure", Severity.INFO),
        ({"x_powered_by": "Express"}, "security.server_disclosure", Severity.INFO),
    ],
)
def test_single_missing_protection_triggers_exactly_one_rule(
    header_changes: dict[str, Any], expected_rule: str, severity: Severity
) -> None:
    issues = analyze([page(headers=with_headers(**header_changes))])
    assert rule_ids(issues) == [expected_rule]
    [issue] = issues
    assert issue.severity == severity
    assert issue.category == Category.SECURITY
    assert issue.recommendation


def test_frame_ancestors_in_csp_replaces_x_frame_options() -> None:
    headers = with_headers(x_frame_options=None, content_security_policy="frame-ancestors 'self'")
    assert analyze([page(headers=headers)]) == []


def test_plain_http_site() -> None:
    issues = analyze([page(url="http://example.com/", headers=with_headers())])
    # HSTS is meaningless over HTTP, so only the HTTPS rule fires.
    assert rule_ids(issues) == ["security.https.missing"]
    assert issues[0].severity == Severity.CRITICAL


def test_localhost_is_exempt_from_https() -> None:
    assert analyze([page(url="http://localhost:8000/", headers=with_headers())]) == []


def test_one_site_wide_issue_with_affected_count() -> None:
    no_csp = with_headers(content_security_policy=None)
    pages = [page(f"{SITE}/{i}", headers=no_csp) for i in range(3)] + [page(f"{SITE}/ok")]
    [issue] = analyze(pages)
    assert issue.affected == 3
    assert issue.url == f"{SITE}/0"
    assert "on 3 of 4 pages" in issue.message


def test_disclosed_values_are_named_in_the_message() -> None:
    headers = with_headers(server="Apache/2.4.41 (Ubuntu)", x_powered_by="PHP/7.4.3")
    [issue] = analyze([page(headers=headers)])
    assert "Server: Apache/2.4.41 (Ubuntu)" in issue.message
    assert "X-Powered-By: PHP/7.4.3" in issue.message


def test_hsts_threshold_comes_from_config() -> None:
    strict = SecurityThresholds(hsts_min_age_days=400)
    assert rule_ids(analyze([page()], strict)) == ["security.hsts.weak"]


def test_error_pages_redirect_aliases_and_files_are_ignored() -> None:
    redirected = page(f"{SITE}/old", headers={})
    redirected.final_url = f"{SITE}/"
    pdf = PageResult(url=f"{SITE}/f.pdf", depth=0, status_code=200, content_type="application/pdf")
    pages = [page(), redirected, page(f"{SITE}/404", headers={}, status=404), pdf]
    assert analyze(pages) == []
