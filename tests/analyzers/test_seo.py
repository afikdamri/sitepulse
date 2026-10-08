from typing import Any

import pytest

from sitepulse.analyzers import AuditData, SeoAnalyzer
from sitepulse.analyzers.seo import extract_seo_facts
from sitepulse.config import AuditConfig, SeoThresholds
from sitepulse.models import Category, Issue, PageResult, Severity

SITE = "https://example.com"
GOOD_TITLE = "Handmade Ceramic Mugs - Free Shipping | Clay Studio"  # 51 chars
GOOD_DESCRIPTION = (
    "Browse handmade ceramic mugs, glazed in small batches in our studio and shipped free "
    "worldwide."
)  # 95 chars


def build_html(
    *,
    title: str | None = GOOD_TITLE,
    description: str | None = GOOD_DESCRIPTION,
    canonical: str | None = f"{SITE}/",
    lang: str | None = "en",
    viewport: bool = True,
    open_graph: bool = True,
    headings: tuple[str, ...] = ("h1", "h2", "h3"),
    head: str = "",
    body: str = "",
) -> str:
    parts = ['<meta charset="utf-8">']
    if title is not None:
        parts.append(f"<title>{title}</title>")
    if description is not None:
        parts.append(f'<meta name="description" content="{description}">')
    if canonical is not None:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    if viewport:
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if open_graph:
        for prop in ("title", "description", "image"):
            parts.append(f'<meta property="og:{prop}" content="x">')
    lang_attr = f' lang="{lang}"' if lang is not None else ""
    heading_html = "".join(f"<{h}>Heading</{h}>" for h in headings)
    return (
        f"<!doctype html><html{lang_attr}><head>{''.join(parts)}{head}</head>"
        f'<body>{heading_html}<img src="/a.png" alt="A mug">{body}</body></html>'
    )


def page(url: str = f"{SITE}/", html: str | None = None, status: int = 200) -> PageResult:
    return PageResult(
        url=url,
        depth=0,
        status_code=status,
        content_type="text/html",
        html=build_html() if html is None else html,
    )


def analyze(pages: list[PageResult], seo: SeoThresholds | None = None) -> list[Issue]:
    config = AuditConfig(start_url=SITE, seo=seo or SeoThresholds())
    return SeoAnalyzer().analyze(AuditData(config=config, pages=pages, links=[]))


def rule_ids(issues: list[Issue]) -> list[str]:
    return sorted(issue.rule_id for issue in issues)


# ---- extraction ----------------------------------------------------------------------------


def test_extract_facts_from_a_complete_page() -> None:
    facts = extract_seo_facts(build_html(), f"{SITE}/")
    assert facts.title == GOOD_TITLE
    assert facts.description == GOOD_DESCRIPTION
    assert facts.canonical == f"{SITE}/"
    assert facts.lang == "en"
    assert facts.has_viewport
    assert facts.open_graph == {"og:title", "og:description", "og:image"}
    assert facts.heading_levels == [1, 2, 3]
    assert facts.images_missing_alt == 0
    assert not facts.noindex


def test_extract_handles_tricky_markup() -> None:
    html = """
        <html><head>
          <title>
             Spaced    out
          </title>
          <META NAME="Description" CONTENT="Upper case attrs">
          <link rel="canonical" href="/canonical-page">
          <meta name="googlebot" content="NOINDEX, follow">
          <meta property="og:image" content="  ">
        </head><body>
          <svg><title>Icon caption</title></svg>
          <img src="a.png" alt=""><img src="b.png">
        </body></html>
    """
    facts = extract_seo_facts(html, f"{SITE}/blog/")
    assert facts.titles == ["Spaced out"]  # whitespace collapsed, svg <title> ignored
    assert facts.description == "Upper case attrs"
    assert facts.canonical == f"{SITE}/canonical-page"  # resolved to absolute
    assert facts.noindex
    assert facts.open_graph == set()  # empty content does not count
    assert facts.images_missing_alt == 1  # alt="" is fine for decorative images
    assert facts.lang is None


# ---- per-page rules --------------------------------------------------------------------------


def test_good_page_has_no_issues() -> None:
    assert analyze([page()]) == []


@pytest.mark.parametrize(
    ("html_options", "expected_rule", "severity"),
    [
        ({"title": None}, "seo.title.missing", Severity.CRITICAL),
        ({"title": "   "}, "seo.title.missing", Severity.CRITICAL),
        ({"title": "x" * 61}, "seo.title.long", Severity.WARNING),
        ({"title": "Home"}, "seo.title.short", Severity.INFO),
        ({"head": "<title>Second</title>"}, "seo.title.multiple", Severity.WARNING),
        ({"description": None}, "seo.description.missing", Severity.WARNING),
        ({"description": "x" * 161}, "seo.description.long", Severity.INFO),
        ({"description": "Too short"}, "seo.description.short", Severity.INFO),
        ({"headings": ("h2",)}, "seo.h1.missing", Severity.WARNING),
        ({"headings": ("h1", "h1", "h2")}, "seo.h1.multiple", Severity.INFO),
        ({"headings": ("h1", "h3")}, "seo.headings.skipped_level", Severity.INFO),
        (
            {"head": '<meta name="robots" content="noindex">'},
            "seo.noindex",
            Severity.WARNING,
        ),
        ({"canonical": None}, "seo.canonical.missing", Severity.INFO),
        (
            {"head": f'<link rel="canonical" href="{SITE}/other">'},
            "seo.canonical.multiple",
            Severity.WARNING,
        ),
        ({"lang": None}, "seo.lang.missing", Severity.WARNING),
        ({"viewport": False}, "seo.viewport.missing", Severity.WARNING),
        ({"body": '<img src="/b.png">'}, "seo.img.alt_missing", Severity.WARNING),
        ({"open_graph": False}, "seo.open_graph.missing", Severity.INFO),
    ],
)
def test_single_defect_triggers_exactly_one_rule(
    html_options: dict[str, Any], expected_rule: str, severity: Severity
) -> None:
    issues = analyze([page(html=build_html(**html_options))])
    assert rule_ids(issues) == [expected_rule]
    [issue] = issues
    assert issue.severity == severity
    assert issue.category == Category.SEO
    assert issue.url == f"{SITE}/"
    assert issue.recommendation


def test_thresholds_come_from_config() -> None:
    strict = SeoThresholds(title_min=60, title_max=70)
    assert rule_ids(analyze([page()], strict)) == ["seo.title.short"]


def test_canonical_pointing_at_broken_page() -> None:
    pages = [
        page(html=build_html(canonical=f"{SITE}/old")),
        page(f"{SITE}/old", status=404),
    ]
    issues = analyze(pages)
    assert rule_ids(issues) == ["seo.canonical.broken"]
    assert "HTTP 404" in issues[0].message


def test_error_pages_and_non_html_are_not_analyzed() -> None:
    pages = [
        page(),
        page(f"{SITE}/missing", html=build_html(title=None), status=404),
        PageResult(url=f"{SITE}/file.pdf", depth=1, status_code=200),
    ]
    assert analyze(pages) == []


def test_redirected_urls_are_analyzed_once() -> None:
    redirected = page(f"{SITE}/old", html=build_html(title=None))
    redirected.final_url = f"{SITE}/new"
    direct = page(f"{SITE}/new", html=build_html(title=None))
    assert rule_ids(analyze([redirected, direct])) == ["seo.title.missing"]


# ---- site-wide rules -------------------------------------------------------------------------


def test_identical_pages_without_canonical_are_duplicate_content() -> None:
    same = build_html(canonical=None)
    issues = analyze([page(f"{SITE}/", same), page(f"{SITE}/index.html", same)])
    site_wide = [i for i in issues if i.rule_id.startswith("seo.duplicate")]
    # Reported once as duplicate content - not again as duplicate title/description.
    assert rule_ids(site_wide) == ["seo.duplicate.content"]
    assert "/, /index.html" in site_wide[0].message


def test_identical_pages_with_shared_canonical_are_fine() -> None:
    same = build_html(canonical=f"{SITE}/")
    assert analyze([page(f"{SITE}/", same), page(f"{SITE}/index.html", same)]) == []


def test_duplicate_titles_and_descriptions_across_different_pages() -> None:
    pages = [
        page(f"{SITE}/a", build_html(canonical=f"{SITE}/a", body="<p>A</p>")),
        page(f"{SITE}/b", build_html(canonical=f"{SITE}/b", body="<p>B</p>")),
    ]
    assert rule_ids(analyze(pages)) == ["seo.duplicate.description", "seo.duplicate.title"]


def test_noindex_and_canonicalized_pages_are_not_counted_as_duplicates() -> None:
    noindex = '<meta name="robots" content="noindex">'
    pages = [
        page(f"{SITE}/a", build_html(canonical=f"{SITE}/a", body="<p>A</p>")),
        page(f"{SITE}/print", build_html(canonical=f"{SITE}/a", body="<p>P</p>")),
        page(f"{SITE}/draft", build_html(canonical=f"{SITE}/draft", head=noindex)),
    ]
    assert rule_ids(analyze(pages)) == ["seo.noindex"]
