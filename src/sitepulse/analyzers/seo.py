"""On-page SEO checks (title, description, headings, canonical, indexing, social tags, alt text)
plus site-wide duplicate detection.

Two layers: `extract_seo_facts` turns HTML into plain data, and the analyzer applies rules to
that data. Rules never touch BeautifulSoup, which keeps them simple to read and test.
"""

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise

from bs4 import BeautifulSoup, Tag

from sitepulse.analyzers.base import AuditData, describe_pages
from sitepulse.config import SeoThresholds
from sitepulse.models import Category, Issue, PageResult, Severity
from sitepulse.parsing import parse_html
from sitepulse.url_utils import resolve_url

REQUIRED_OPEN_GRAPH = ("og:title", "og:description", "og:image")
_HEADING = re.compile(r"^h[1-6]$")


@dataclass
class SeoFacts:
    titles: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    heading_levels: list[int] = field(default_factory=list)  # in document order
    canonicals: list[str] = field(default_factory=list)  # absolute URLs
    noindex: bool = False
    lang: str | None = None
    has_viewport: bool = False
    open_graph: set[str] = field(default_factory=set)
    images_missing_alt: int = 0

    @property
    def title(self) -> str:
        return self.titles[0] if self.titles else ""

    @property
    def description(self) -> str:
        return self.descriptions[0] if self.descriptions else ""

    @property
    def canonical(self) -> str | None:
        return self.canonicals[0] if self.canonicals else None


def extract_seo_facts(html: str, page_url: str) -> SeoFacts:
    soup = parse_html(html)
    facts = SeoFacts()

    # <title> inside inline <svg> is an image caption, not the page title.
    facts.titles = [_text(t) for t in soup.find_all("title") if t.find_parent("svg") is None]
    facts.descriptions = [
        " ".join(str(meta.get("content", "")).split())
        for meta in _meta(soup, "name", "description")
    ]
    facts.heading_levels = [int(h.name[1]) for h in soup.find_all(_HEADING)]

    for link in soup.find_all("link", href=True):
        if "canonical" in {rel.lower() for rel in link.get("rel") or []}:
            resolved = resolve_url(page_url, str(link["href"]))
            if resolved is not None:
                facts.canonicals.append(resolved)

    robots = _meta(soup, "name", "robots") + _meta(soup, "name", "googlebot")
    facts.noindex = any("noindex" in str(m.get("content", "")).lower() for m in robots)

    html_tag = soup.find("html")
    lang = str(html_tag.get("lang", "")).strip() if isinstance(html_tag, Tag) else ""
    facts.lang = lang or None
    facts.has_viewport = bool(_meta(soup, "name", "viewport"))
    facts.open_graph = {
        str(meta["property"]).lower()
        for meta in soup.find_all("meta", attrs={"property": True, "content": True})
        if str(meta["property"]).lower().startswith("og:") and str(meta["content"]).strip()
    }
    # alt="" is valid (decorative image); only a missing attribute is a problem.
    facts.images_missing_alt = len(soup.find_all("img", alt=False))
    return facts


def _text(tag: Tag) -> str:
    return " ".join(tag.get_text().split())


def _meta(soup: BeautifulSoup, attr: str, value: str) -> list[Tag]:
    return list(soup.find_all("meta", attrs={attr: re.compile(f"^{value}$", re.IGNORECASE)}))


@dataclass
class _AnalyzedPage:
    url: str
    facts: SeoFacts
    content_hash: str


class SeoAnalyzer:
    category = Category.SEO

    def analyze(self, data: AuditData) -> list[Issue]:
        pages = _analyzable_pages(data.pages)
        status_by_url: dict[str, int | None] = {}
        for crawled in data.pages:
            status_by_url[crawled.url] = crawled.status_code
            if crawled.final_url:
                status_by_url[crawled.final_url] = crawled.status_code

        issues: list[Issue] = []
        for page in pages:
            issues.extend(self._page_issues(page, data.config.seo, status_by_url))
        issues.extend(self._duplicate_content(pages))
        indexable = _deduplicated_indexable(pages)
        issues.extend(self._duplicates(indexable, "title", lambda f: f.title))
        issues.extend(self._duplicates(indexable, "description", lambda f: f.description))
        return issues

    # ---- per-page rules -------------------------------------------------------------------

    def _page_issues(
        self, page: _AnalyzedPage, limits: SeoThresholds, status_by_url: dict[str, int | None]
    ) -> list[Issue]:
        f, url = page.facts, page.url
        issues: list[Issue] = []

        def add(rule: str, severity: Severity, message: str, fix: str) -> None:
            issues.append(self._issue(rule, severity, message, fix, url))

        # Title
        if not f.title:
            add(
                "seo.title.missing",
                Severity.CRITICAL,
                "Page has no <title>",
                "Add a unique, descriptive <title> - it is the headline shown in search results.",
            )
        elif len(f.title) > limits.title_max:
            add(
                "seo.title.long",
                Severity.WARNING,
                f'Title is {len(f.title)} chars (max {limits.title_max}): "{f.title}"',
                f"Shorten the title to under {limits.title_max} characters so search engines "
                "don't truncate it; put the key words first.",
            )
        elif len(f.title) < limits.title_min:
            add(
                "seo.title.short",
                Severity.INFO,
                f'Title is only {len(f.title)} chars (min {limits.title_min}): "{f.title}"',
                "Make the title more descriptive, e.g. 'Topic - Key detail | Brand'.",
            )
        if len(f.titles) > 1:
            add(
                "seo.title.multiple",
                Severity.WARNING,
                f"Page has {len(f.titles)} <title> tags",
                "Keep exactly one <title> in <head>; search engines may pick the wrong one.",
            )

        # Meta description
        if not f.description:
            add(
                "seo.description.missing",
                Severity.WARNING,
                "Page has no meta description",
                'Add <meta name="description" content="..."> summarizing the page in '
                f"{limits.description_min}-{limits.description_max} characters; it is the "
                "snippet under the title in search results.",
            )
        elif len(f.description) > limits.description_max:
            add(
                "seo.description.long",
                Severity.INFO,
                f"Meta description is {len(f.description)} chars (max {limits.description_max})",
                f"Trim it to {limits.description_max} characters so it isn't cut off.",
            )
        elif len(f.description) < limits.description_min:
            add(
                "seo.description.short",
                Severity.INFO,
                f"Meta description is only {len(f.description)} chars "
                f"(min {limits.description_min})",
                "Expand it into a compelling one- or two-sentence summary of the page.",
            )

        # Headings
        h1_count = f.heading_levels.count(1)
        if h1_count == 0:
            add(
                "seo.h1.missing",
                Severity.WARNING,
                "Page has no <h1> heading",
                "Add one <h1> that states the main topic of the page.",
            )
        elif h1_count > 1:
            add(
                "seo.h1.multiple",
                Severity.INFO,
                f"Page has {h1_count} <h1> headings",
                "Use a single <h1> for the main topic and <h2>-<h6> for sections.",
            )
        skip = _first_skipped_level(f.heading_levels)
        if skip is not None:
            add(
                "seo.headings.skipped_level",
                Severity.INFO,
                f"Heading levels skip from <h{skip[0]}> to <h{skip[1]}>",
                "Nest headings in order (h1 > h2 > h3) so the outline makes sense to search "
                "engines and screen readers.",
            )

        # Indexing
        if f.noindex:
            add(
                "seo.noindex",
                Severity.WARNING,
                "Page is marked noindex and will not appear in search results",
                "Remove the noindex robots meta tag unless hiding this page is intentional.",
            )
        if len(set(f.canonicals)) > 1:
            add(
                "seo.canonical.multiple",
                Severity.WARNING,
                f"Page declares {len(f.canonicals)} different canonical URLs",
                'Keep a single <link rel="canonical">; conflicting ones are ignored.',
            )
        elif f.canonical is None:
            add(
                "seo.canonical.missing",
                Severity.INFO,
                "Page has no canonical URL",
                'Add <link rel="canonical" href="..."> pointing at the preferred URL to '
                "prevent duplicate-content problems.",
            )
        if f.canonical is not None and (status_by_url.get(f.canonical) or 0) >= 400:
            add(
                "seo.canonical.broken",
                Severity.CRITICAL,
                f"Canonical URL {f.canonical} returns HTTP {status_by_url[f.canonical]}",
                "Point the canonical at a live page (usually this page's own URL).",
            )

        # Mobile & accessibility
        if f.lang is None:
            add(
                "seo.lang.missing",
                Severity.WARNING,
                "The <html> tag has no lang attribute",
                'Declare the language, e.g. <html lang="en">, for search engines and screen '
                "readers.",
            )
        if not f.has_viewport:
            add(
                "seo.viewport.missing",
                Severity.WARNING,
                "Page has no viewport meta tag",
                'Add <meta name="viewport" content="width=device-width, initial-scale=1">; '
                "Google indexes the mobile version of pages.",
            )
        if f.images_missing_alt:
            add(
                "seo.img.alt_missing",
                Severity.WARNING,
                f"{f.images_missing_alt} image(s) have no alt attribute",
                'Describe each image in alt="..." (or alt="" for purely decorative images).',
            )

        # Social sharing
        missing_og = [tag for tag in REQUIRED_OPEN_GRAPH if tag not in f.open_graph]
        if missing_og:
            add(
                "seo.open_graph.missing",
                Severity.INFO,
                f"Missing Open Graph tags: {', '.join(missing_og)}",
                "Add og:title, og:description and og:image so links to this page look good "
                "when shared on social media and chat apps.",
            )
        return issues

    # ---- site-wide rules ------------------------------------------------------------------

    def _duplicate_content(self, pages: list[_AnalyzedPage]) -> list[Issue]:
        groups: dict[str, list[_AnalyzedPage]] = defaultdict(list)
        for page in pages:
            groups[page.content_hash].append(page)

        issues = []
        for group in groups.values():
            if len(group) < 2:
                continue
            canonicals = {page.facts.canonical for page in group}
            if len(canonicals) == 1 and None not in canonicals:
                continue  # every copy points at the same canonical URL: handled correctly
            urls = [page.url for page in group]
            issues.append(
                self._issue(
                    "seo.duplicate.content",
                    Severity.WARNING,
                    f"Identical content served at {len(urls)} URLs: {describe_pages(urls)}",
                    "Pick one URL; 301-redirect the others to it or add a matching "
                    '<link rel="canonical"> on every copy.',
                    urls[0],
                )
            )
        return issues

    def _duplicates(
        self,
        pages: list[_AnalyzedPage],
        what: str,
        value_of: Callable[[SeoFacts], str],
    ) -> list[Issue]:
        groups: dict[str, list[str]] = defaultdict(list)
        for page in pages:
            value = value_of(page.facts)
            if value:
                groups[value.casefold()].append(page.url)

        return [
            self._issue(
                f"seo.duplicate.{what}",
                Severity.WARNING,
                f"{len(urls)} pages share the same {what}: {describe_pages(urls)}",
                f"Give every page a unique {what} that describes its specific content.",
                urls[0],
            )
            for urls in groups.values()
            if len(urls) > 1
        ]

    def _issue(
        self, rule_id: str, severity: Severity, message: str, recommendation: str, url: str
    ) -> Issue:
        return Issue(
            rule_id=rule_id,
            category=self.category,
            severity=severity,
            message=message,
            recommendation=recommendation,
            url=url,
        )


def _analyzable_pages(pages: list[PageResult]) -> list[_AnalyzedPage]:
    """Successful HTML pages, once per final URL (two links redirecting to one page count once)."""
    analyzed: dict[str, _AnalyzedPage] = {}
    for page in pages:
        if page.html is None or page.status_code is None or page.status_code >= 300:
            continue
        url = page.final_url or page.url
        if url not in analyzed:
            content_hash = hashlib.sha256(page.html.encode()).hexdigest()
            analyzed[url] = _AnalyzedPage(url, extract_seo_facts(page.html, url), content_hash)
    return list(analyzed.values())


def _deduplicated_indexable(pages: list[_AnalyzedPage]) -> list[_AnalyzedPage]:
    """Pages that compete in search results, for duplicate title/description checks.

    Excludes noindex pages, pages that canonicalize to another URL, and exact content copies
    (already reported as duplicate content - no need to report their titles again).
    """
    seen_hashes: set[str] = set()
    result = []
    for page in pages:
        f = page.facts
        if f.noindex or (f.canonical is not None and f.canonical != page.url):
            continue
        if page.content_hash in seen_hashes:
            continue
        seen_hashes.add(page.content_hash)
        result.append(page)
    return result


def _first_skipped_level(levels: list[int]) -> tuple[int, int] | None:
    for previous, current in pairwise(levels):
        if current > previous + 1:
            return previous, current
    return None
