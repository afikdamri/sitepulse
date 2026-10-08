"""HTTP security headers: HTTPS, HSTS, CSP, clickjacking protection, MIME sniffing, referrer
leaks and server version disclosure.

Headers are almost always configured once for the whole server, so each rule produces one
site-wide issue whose `affected` count is the number of pages missing the protection.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from sitepulse.analyzers.base import AuditData, describe_pages
from sitepulse.config import SecurityThresholds
from sitepulse.models import Category, Issue, PageResult, Severity
from sitepulse.parsing import parse_html

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_MAX_AGE = re.compile(r"max-age\s*=\s*\"?(\d+)", re.IGNORECASE)
_VERSION = re.compile(r"\d")  # "nginx/1.18.0" exposes a version; "nginx" alone does not


@dataclass
class SecurityFacts:
    """What a single page's response tells us, independent of any judgement."""

    url: str
    is_https: bool
    is_local: bool  # localhost dev servers don't need HTTPS
    hsts_max_age: int | None  # None = header missing or unparsable
    has_csp: bool
    frame_protected: bool  # X-Frame-Options or CSP frame-ancestors
    nosniff: bool
    has_referrer_policy: bool
    disclosed: list[str]  # e.g. ["Server: nginx/1.18.0", "X-Powered-By: PHP/8.1"]


def extract_security_facts(page: PageResult) -> SecurityFacts:
    url = page.final_url or page.url
    parts = urlsplit(url)
    headers = page.headers
    csp = headers.get("content-security-policy", "")
    # A <meta http-equiv> CSP is valid too (but can't carry frame-ancestors).
    has_meta_csp = page.html is not None and _has_meta_csp(page.html)
    frame_options = headers.get("x-frame-options", "").strip().lower()

    match = _MAX_AGE.search(headers.get("strict-transport-security", ""))
    disclosed = []
    server = headers.get("server", "")
    if _VERSION.search(server):
        disclosed.append(f"Server: {server}")
    if powered_by := headers.get("x-powered-by"):
        disclosed.append(f"X-Powered-By: {powered_by}")

    return SecurityFacts(
        url=url,
        is_https=parts.scheme == "https",
        is_local=(parts.hostname or "") in LOCAL_HOSTS
        or (parts.hostname or "").endswith(".localhost"),
        hsts_max_age=int(match.group(1)) if match else None,
        has_csp=bool(csp.strip()) or has_meta_csp,
        frame_protected=frame_options in ("deny", "sameorigin") or "frame-ancestors" in csp.lower(),
        nosniff=headers.get("x-content-type-options", "").strip().lower() == "nosniff",
        has_referrer_policy=bool(headers.get("referrer-policy", "").strip()),
        disclosed=disclosed,
    )


def _has_meta_csp(html: str) -> bool:
    for meta in parse_html(html).find_all("meta", attrs={"http-equiv": True}):
        if str(meta["http-equiv"]).strip().lower() == "content-security-policy":
            return bool(str(meta.get("content", "")).strip())
    return False


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    severity: Severity
    fails: Callable[[SecurityFacts, SecurityThresholds], bool]
    problem: str  # completes "<problem> on N of M pages"
    recommendation: str


RULES = [
    _Rule(
        "security.https.missing",
        Severity.CRITICAL,
        lambda f, _: not f.is_https and not f.is_local,
        "Served over insecure HTTP",
        "Serve the site over HTTPS (free certificates from Let's Encrypt) and 301-redirect "
        "every http:// URL to https://.",
    ),
    _Rule(
        "security.hsts.missing",
        Severity.WARNING,
        lambda f, _: f.is_https and not f.hsts_max_age,
        "No HSTS protection (Strict-Transport-Security missing or max-age=0)",
        "Send 'Strict-Transport-Security: max-age=31536000; includeSubDomains' so browsers "
        "refuse to ever load the site over plain HTTP. Note: max-age=0 switches HSTS off.",
    ),
    _Rule(
        "security.hsts.weak",
        Severity.INFO,
        lambda f, t: (
            f.is_https
            and bool(f.hsts_max_age)
            and (f.hsts_max_age or 0) < t.hsts_min_age_days * 86_400
        ),
        "HSTS max-age is shorter than recommended",
        "Raise the HSTS max-age to at least 6 months (15552000 seconds); one year is typical.",
    ),
    _Rule(
        "security.csp.missing",
        Severity.WARNING,
        lambda f, _: not f.has_csp,
        "No Content-Security-Policy",
        "Add a Content-Security-Policy that whitelists where scripts, styles and images may "
        "load from; it is the main defense against cross-site scripting (XSS). Start with "
        "Content-Security-Policy-Report-Only to test it safely.",
    ),
    _Rule(
        "security.clickjacking.missing",
        Severity.WARNING,
        lambda f, _: not f.frame_protected,
        "No clickjacking protection (X-Frame-Options / frame-ancestors)",
        "Send 'X-Frame-Options: DENY' (or SAMEORIGIN), or add frame-ancestors 'self' to the "
        "CSP, so other sites can't embed your pages in invisible frames.",
    ),
    _Rule(
        "security.nosniff.missing",
        Severity.INFO,
        lambda f, _: not f.nosniff,
        "X-Content-Type-Options: nosniff missing",
        "Send 'X-Content-Type-Options: nosniff' so browsers don't execute files with a "
        "misleading content type.",
    ),
    _Rule(
        "security.referrer_policy.missing",
        Severity.INFO,
        lambda f, _: not f.has_referrer_policy,
        "No Referrer-Policy",
        "Send 'Referrer-Policy: strict-origin-when-cross-origin' so full URLs (which may "
        "contain tokens or search terms) don't leak to other sites.",
    ),
    _Rule(
        "security.server_disclosure",
        Severity.INFO,
        lambda f, _: bool(f.disclosed),
        "Server software version disclosed",
        "Hide version numbers (e.g. nginx 'server_tokens off', remove X-Powered-By); they "
        "tell attackers exactly which known vulnerabilities to try.",
    ),
]


class SecurityAnalyzer:
    category = Category.SECURITY

    def analyze(self, data: AuditData) -> list[Issue]:
        facts = [extract_security_facts(page) for page in _content_pages(data.pages)]
        issues: list[Issue] = []
        for rule in RULES:
            failing = [f for f in facts if rule.fails(f, data.config.security)]
            if not failing:
                continue
            urls = [f.url for f in failing]
            detail = ""
            if rule.rule_id == "security.server_disclosure":
                detail = f" ({', '.join(sorted({d for f in failing for d in f.disclosed}))})"
            issues.append(
                Issue(
                    rule_id=rule.rule_id,
                    category=self.category,
                    severity=rule.severity,
                    message=f"{rule.problem}{detail} on {len(failing)} of {len(facts)} pages: "
                    f"{describe_pages(urls)}",
                    recommendation=rule.recommendation,
                    url=urls[0],
                    affected=len(failing),
                )
            )
        return issues


def _content_pages(pages: list[PageResult]) -> list[PageResult]:
    """Successful HTML pages, once per final URL."""
    seen: set[str] = set()
    result = []
    for page in pages:
        url = page.final_url or page.url
        if page.is_html and (page.status_code or 0) in range(200, 400) and url not in seen:
            seen.add(url)
            result.append(page)
    return result
