from collections.abc import Callable

import httpx
import pytest
import respx

from sitepulse.auditor import AuditError, run_audit
from sitepulse.config import AuditConfig

SITE = "https://example.com"
Html = Callable[..., str]


async def test_run_audit_builds_report(mock_site: respx.MockRouter, html: Html) -> None:
    mock_site.get(f"{SITE}/robots.txt").respond(404)
    mock_site.get(f"{SITE}/").respond(200, html=html("/a"))
    mock_site.get(f"{SITE}/a").respond(200, html=html())

    seen: list[str] = []
    report = await run_audit(AuditConfig(start_url=SITE), on_page=lambda p: seen.append(p.url))

    assert report.target_url == f"{SITE}/"
    assert [p.url for p in report.pages] == [f"{SITE}/", f"{SITE}/a"]
    assert sorted(seen) == sorted(p.url for p in report.pages)  # progress callback fired
    assert report.duration_s >= 0


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
