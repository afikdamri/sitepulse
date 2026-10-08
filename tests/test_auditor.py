from collections.abc import Callable

import httpx
import pytest
import respx

from sitepulse.auditor import AuditError, run_audit
from sitepulse.config import AuditConfig
from sitepulse.models import LinkResult, PageResult

SITE = "https://example.com"
Html = Callable[..., str]


class RecordingProgress:
    def __init__(self) -> None:
        self.pages: list[str] = []
        self.links_total: int | None = None
        self.links: list[str] = []

    def page_done(self, page: PageResult) -> None:
        self.pages.append(page.url)

    def links_started(self, total: int) -> None:
        self.links_total = total

    def link_done(self, link: LinkResult) -> None:
        self.links.append(link.url)


async def test_run_audit_crawls_checks_links_and_analyzes(
    mock_site: respx.MockRouter, html: Html
) -> None:
    mock_site.get(f"{SITE}/robots.txt").respond(404)
    mock_site.get(f"{SITE}/").respond(200, html=html("/a", "/gone", body='<img src="/x.png">'))
    mock_site.get(f"{SITE}/a").respond(200, html=html())
    mock_site.get(f"{SITE}/gone").respond(404)
    mock_site.head(f"{SITE}/x.png").respond(200)

    progress = RecordingProgress()
    report = await run_audit(AuditConfig(start_url=SITE), progress=progress)

    assert report.target_url == f"{SITE}/"
    assert [p.url for p in report.pages] == [f"{SITE}/", f"{SITE}/a", f"{SITE}/gone"]
    assert {link.url for link in report.links} == {f"{SITE}/a", f"{SITE}/gone", f"{SITE}/x.png"}
    assert [issue.rule_id for issue in report.issues] == ["links.internal.broken"]
    # progress hooks fired for every page and link
    assert sorted(progress.pages) == sorted(p.url for p in report.pages)
    assert progress.links_total == 3
    assert len(progress.links) == 3


async def test_unreachable_start_url_raises(mock_site: respx.MockRouter) -> None:
    mock_site.get(f"{SITE}/robots.txt").mock(side_effect=httpx.ConnectError("dns"))
    mock_site.get(f"{SITE}/").mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(AuditError, match="Could not reach"):
        await run_audit(AuditConfig(start_url=SITE))


async def test_start_url_blocked_by_robots_raises(mock_site: respx.MockRouter) -> None:
    mock_site.get(f"{SITE}/robots.txt").respond(200, text="User-agent: *\nDisallow: /\n")
    with pytest.raises(AuditError, match="--ignore-robots"):
        await run_audit(AuditConfig(start_url=SITE))


async def test_ignore_robots_skips_robots_txt(mock_site: respx.MockRouter, html: Html) -> None:
    robots = mock_site.get(f"{SITE}/robots.txt").respond(200, text="User-agent: *\nDisallow: /")
    mock_site.get(f"{SITE}/").respond(200, html=html())
    report = await run_audit(AuditConfig(start_url=SITE, respect_robots=False))
    assert len(report.pages) == 1
    assert not robots.called


async def test_robots_notes_are_reported(mock_site: respx.MockRouter, html: Html) -> None:
    # urllib.robotparser only understands integer Crawl-delay values. Only one page is fetched
    # here, and the first request is never delayed, so the test stays fast.
    mock_site.get(f"{SITE}/robots.txt").respond(
        200, text="User-agent: *\nDisallow: /private\nCrawl-delay: 1\n"
    )
    mock_site.get(f"{SITE}/").respond(200, html=html("/private"))
    report = await run_audit(AuditConfig(start_url=SITE))
    assert any("Crawl-delay" in note for note in report.notes)
    assert any("1 URL(s) skipped" in note for note in report.notes)


async def test_no_external_skips_external_links(mock_site: respx.MockRouter, html: Html) -> None:
    mock_site.get(f"{SITE}/robots.txt").respond(404)
    mock_site.get(f"{SITE}/").respond(200, html=html("https://other.com/"))
    external = mock_site.head("https://other.com/").respond(200)
    report = await run_audit(AuditConfig(start_url=SITE, check_external=False))
    assert report.links == []
    assert not external.called
    assert any("--no-external" in note for note in report.notes)
