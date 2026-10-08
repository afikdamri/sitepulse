"""Human-readable titles for every rule_id, used to label recommendations.

A test (`tests/test_rules.py`) scans the analyzers and fails if a rule_id is missing here.
"""

RULE_TITLES: dict[str, str] = {
    # Links
    "links.internal.broken": "Broken internal links",
    "links.resource.broken": "Broken images, scripts or stylesheets",
    "links.unreachable": "Unreachable links (timeouts, DNS errors)",
    "links.external.broken": "Broken external links",
    "links.external.unverifiable": "External links blocking automated checks",
    "links.redirect.insecure": "Redirects from HTTPS to insecure HTTP",
    "links.redirect.chain": "Redirect chains",
    "links.internal.redirect": "Internal links pointing at redirects",
    "links.mixed_content": "Insecure HTTP resources on HTTPS pages",
    # SEO
    "seo.title.missing": "Missing page titles",
    "seo.title.long": "Page titles too long",
    "seo.title.short": "Page titles too short",
    "seo.title.multiple": "Multiple <title> tags",
    "seo.description.missing": "Missing meta descriptions",
    "seo.description.long": "Meta descriptions too long",
    "seo.description.short": "Meta descriptions too short",
    "seo.h1.missing": "Missing <h1> headings",
    "seo.h1.multiple": "Multiple <h1> headings",
    "seo.headings.skipped_level": "Skipped heading levels",
    "seo.noindex": "Pages hidden from search engines (noindex)",
    "seo.canonical.missing": "Missing canonical URLs",
    "seo.canonical.multiple": "Conflicting canonical URLs",
    "seo.canonical.broken": "Canonical URLs pointing at broken pages",
    "seo.lang.missing": "Missing page language",
    "seo.viewport.missing": "Not mobile-friendly (no viewport)",
    "seo.img.alt_missing": "Images without alt text",
    "seo.open_graph.missing": "Missing social sharing tags (Open Graph)",
    "seo.duplicate.content": "Duplicate content at multiple URLs",
    "seo.duplicate.title": "Duplicate page titles",
    "seo.duplicate.description": "Duplicate meta descriptions",
    # Performance
    "perf.page.slow": "Slow server responses",
    "perf.html.large": "Oversized HTML documents",
    "perf.compression.missing": "Compression disabled",
    "perf.ttfb.median_high": "High typical server response time",
    "perf.ttfb.inconsistent": "Erratic server response times",
    # Security
    "security.https.missing": "Pages served over insecure HTTP",
    "security.hsts.missing": "HSTS missing or disabled",
    "security.hsts.weak": "HSTS max-age too short",
    "security.csp.missing": "No Content-Security-Policy",
    "security.clickjacking.missing": "No clickjacking protection",
    "security.nosniff.missing": "MIME sniffing not disabled (nosniff)",
    "security.referrer_policy.missing": "No Referrer-Policy",
    "security.server_disclosure": "Server version disclosed",
}


def rule_title(rule_id: str) -> str:
    return RULE_TITLES.get(rule_id, rule_id)
