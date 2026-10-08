import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx
import respx

from sitepulse.config import AuditConfig
from sitepulse.crawler import Crawler, RateLimiter
from sitepulse.robots import RobotsPolicy

SITE = "https://example.com"
Html = Callable[..., str]


def config(**overrides: Any) -> AuditConfig:
    return AuditConfig(start_url=f"{SITE}/", **overrides)


async def test_crawls_whole_site_in_bfs_order_without_revisiting(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    routes = {
        "/": mock_site.get(f"{SITE}/").respond(200, html=html("/a", "/b")),
        "/a": mock_site.get(f"{SITE}/a").respond(200, html=html("/c", "/")),
        "/b": mock_site.get(f"{SITE}/b").respond(200, html=html("/a", "/b")),
        "/c": mock_site.get(f"{SITE}/c").respond(200, html=html()),
    }
    pages = await Crawler(config(), client).crawl()

    assert [p.url for p in pages] == [f"{SITE}/", f"{SITE}/a", f"{SITE}/b", f"{SITE}/c"]
    assert [p.depth for p in pages] == [0, 1, 1, 2]
    assert all(route.call_count == 1 for route in routes.values())  # cycles don't cause refetches


async def test_respects_max_pages(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html(*[f"/p{i}" for i in range(10)]))
    mock_site.get(url__regex=rf"{SITE}/p\d+").respond(200, html=html())
    pages = await Crawler(config(max_pages=4), client).crawl()
    assert len(pages) == 4


async def test_respects_max_depth(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/a"))
    mock_site.get(f"{SITE}/a").respond(200, html=html("/deep"))
    deep = mock_site.get(f"{SITE}/deep").respond(200, html=html())
    pages = await Crawler(config(max_depth=1), client).crawl()
    assert [p.url for p in pages] == [f"{SITE}/", f"{SITE}/a"]
    assert not deep.called


async def test_external_links_are_recorded_but_not_crawled(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("https://other.com/x"))
    external = mock_site.get("https://other.com/x").respond(200, html=html())
    pages = await Crawler(config(), client).crawl()
    assert pages[0].links == ["https://other.com/x"]
    assert not external.called


async def test_error_pages_are_recorded_and_not_followed(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/missing"))
    mock_site.get(f"{SITE}/missing").respond(404, html=html("/from-404"))
    from_404 = mock_site.get(f"{SITE}/from-404").respond(200, html=html())
    pages = await Crawler(config(), client).crawl()
    assert pages[1].status_code == 404
    assert pages[1].links == []
    assert not from_404.called


async def test_network_failures_become_page_errors(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/slow", "/down"))
    mock_site.get(f"{SITE}/slow").mock(side_effect=httpx.ReadTimeout("slow"))
    mock_site.get(f"{SITE}/down").mock(side_effect=httpx.ConnectError("refused"))
    pages = {p.url: p for p in await Crawler(config(), client).crawl()}
    assert pages[f"{SITE}/slow"].error == "timeout"
    assert pages[f"{SITE}/slow"].status_code is None
    assert "ConnectError" in (pages[f"{SITE}/down"].error or "")


async def test_redirects_are_followed_and_target_not_refetched(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/old"))
    mock_site.get(f"{SITE}/old").respond(301, headers={"Location": f"{SITE}/new"})
    new = mock_site.get(f"{SITE}/new").respond(200, html=html("/new"))  # links to itself
    pages = await Crawler(config(), client).crawl()

    old = pages[1]
    assert old.url == f"{SITE}/old"
    assert old.final_url == f"{SITE}/new"
    assert old.redirect_chain == [f"{SITE}/old"]
    assert new.call_count == 1


async def test_start_url_redirect_to_www_still_crawls_site(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(301, headers={"Location": "https://www.example.com/"})
    mock_site.get("https://www.example.com/").respond(200, html=html("/about"))
    about = mock_site.get("https://www.example.com/about").respond(200, html=html())
    await Crawler(config(), client).crawl()
    assert about.called


async def test_robots_disallowed_urls_are_skipped(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/private/x", "/public"))
    private = mock_site.get(f"{SITE}/private/x").respond(200, html=html())
    mock_site.get(f"{SITE}/public").respond(200, html=html())
    robots = RobotsPolicy.from_text("User-agent: *\nDisallow: /private\n")

    crawler = Crawler(config(), client, robots)
    pages = await crawler.crawl()

    assert [p.url for p in pages] == [f"{SITE}/", f"{SITE}/public"]
    assert crawler.blocked_by_robots == [f"{SITE}/private/x"]
    assert not private.called


async def test_non_html_is_not_downloaded_or_parsed(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    mock_site.get(f"{SITE}/").respond(200, html=html("/file.pdf"))
    mock_site.get(f"{SITE}/file.pdf").respond(
        200, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"}
    )
    pdf = (await Crawler(config(), client).crawl())[1]
    assert pdf.status_code == 200
    assert not pdf.is_html
    assert pdf.html is None
    assert pdf.size_bytes == len(b"%PDF-1.7")  # from Content-Length


async def test_records_timings_and_size(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    body = html()
    mock_site.get(f"{SITE}/").respond(200, html=body)
    page = (await Crawler(config(), client).crawl())[0]
    assert page.ttfb_ms is not None and page.response_time_ms is not None
    assert 0 <= page.ttfb_ms <= page.response_time_ms
    assert page.size_bytes == len(body)
    assert page.html == body


async def test_never_exceeds_concurrency_limit(
    mock_site: respx.MockRouter, client: httpx.AsyncClient, html: Html
) -> None:
    in_flight = 0
    peak = 0

    async def slow_page(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return httpx.Response(200, html=html())

    mock_site.get(f"{SITE}/").respond(200, html=html(*[f"/p{i}" for i in range(12)]))
    mock_site.get(url__regex=rf"{SITE}/p\d+").mock(side_effect=slow_page)
    pages = await Crawler(config(concurrency=3), client).crawl()

    assert len(pages) == 13
    assert 1 < peak <= 3  # really parallel, but never above the limit


async def test_rate_limiter_spaces_out_requests() -> None:
    limiter = RateLimiter(0.05)
    start = time.monotonic()
    await asyncio.gather(*(limiter.wait() for _ in range(3)))
    assert time.monotonic() - start >= 0.1  # 3 slots -> at least 2 intervals
