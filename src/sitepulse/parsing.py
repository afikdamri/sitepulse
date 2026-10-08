"""Extract outgoing links and page resources from HTML."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from sitepulse.url_utils import resolve_url

# <link rel="..."> values that point at files the browser actually downloads.
_RESOURCE_LINK_RELS = {"stylesheet", "icon", "shortcut", "apple-touch-icon", "preload"}


@dataclass
class ExtractedLinks:
    links: list[str] = field(default_factory=list)  # <a href>: navigable pages
    resources: list[str] = field(default_factory=list)  # images, scripts, stylesheets


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_links(html: str, page_url: str) -> ExtractedLinks:
    soup = parse_html(html)

    # <base href> changes how every relative URL on the page is resolved.
    base_url = page_url
    base = soup.find("base", href=True)
    if base is not None:
        base_url = resolve_url(page_url, str(base["href"])) or page_url

    links = _resolve_all(base_url, (str(a["href"]) for a in soup.find_all("a", href=True)))

    raw_resources: list[str] = []
    for tag in soup.find_all(["img", "script", "iframe", "source"], src=True):
        raw_resources.append(str(tag["src"]))
    for tag in soup.find_all("link", href=True):
        rels = {rel.lower() for rel in tag.get("rel") or []}
        if rels & _RESOURCE_LINK_RELS:
            raw_resources.append(str(tag["href"]))
    resources = _resolve_all(base_url, raw_resources)

    return ExtractedLinks(links=links, resources=resources)


def _resolve_all(base_url: str, hrefs: Iterable[str]) -> list[str]:
    """Resolve and de-duplicate, keeping first-seen order (dicts preserve insertion order)."""
    resolved: dict[str, None] = {}
    for href in hrefs:
        url = resolve_url(base_url, href)
        if url is not None:
            resolved[url] = None
    return list(resolved)
