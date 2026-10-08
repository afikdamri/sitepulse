import httpx
import respx

from sitepulse.config import AuditConfig
from sitepulse.link_checker import LinkChecker
from sitepulse.models import LinkResult, PageResult
from sitepulse.robots import RobotsPolicy

SITE = "https://example.com"


def page(
    url: str, links: list[str] | None = None, resources: list[str] | None = None
) -> PageResult:
    return PageResult(
        url=url, depth=0, status_code=200, links=links or [], resources=resources or []
    )


async def check(
    client: httpx.AsyncClient, pages: list[PageResult], config: AuditConfig | None = None
) -> tuple[list[LinkResult], LinkChecker]:
    checker = LinkChecker(config or AuditConfig(start_url=SITE), client)
    results = await checker.check(checker.collect_targets(pages), pages)
    return results, checker


def by_url(results: list[LinkResult]) -> dict[str, LinkResult]:
    return {result.url: result for result in results}


def test_collect_targets_dedupes_and_tracks_sources() -> None:
    pages = [
        page(f"{SITE}/", links=[f"{SITE}/a", "https://other.com/"], resources=[f"{SITE}/x.png"]),
        page(f"{SITE}/b", links=[f"{SITE}/a"], resources=[f"{SITE}/a"]),
    ]
    checker = LinkChecker(AuditConfig(start_url=SITE), httpx.AsyncClient())
    targets = {target.url: target for target in checker.collect_targets(pages)}

    assert targets[f"{SITE}/a"].found_on == [f"{SITE}/", f"{SITE}/b"]
    assert targets[f"{SITE}/a"].is_resource is False  # also used as a page link
    assert targets[f"{SITE}/x.png"].is_resource is True
    assert targets["https://other.com/"].is_internal is False


async def test_crawled_pages_are_reused_without_requests(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    pages = [
        page(f"{SITE}/", links=[f"{SITE}/missing"]),
        PageResult(url=f"{SITE}/missing", depth=1, status_code=404),
    ]
    results, _ = await check(client, pages)
    assert by_url(results)[f"{SITE}/missing"].status_code == 404
    assert mock_site.calls.call_count == 0


async def test_head_success(mock_site: respx.MockRouter, client: httpx.AsyncClient) -> None:
    mock_site.head("https://other.com/ok").respond(200)
    results, _ = await check(client, [page(f"{SITE}/", links=["https://other.com/ok"])])
    link = by_url(results)["https://other.com/ok"]
    assert link.status_code == 200
    assert not link.is_broken


async def test_head_rejected_falls_back_to_get(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.head("https://other.com/no-head").respond(405)
    get = mock_site.get("https://other.com/no-head").respond(200)
    results, _ = await check(client, [page(f"{SITE}/", links=["https://other.com/no-head"])])
    assert by_url(results)["https://other.com/no-head"].status_code == 200
    assert get.called


async def test_really_broken_link(mock_site: respx.MockRouter, client: httpx.AsyncClient) -> None:
    mock_site.head(f"{SITE}/img.png").respond(404)
    mock_site.get(f"{SITE}/img.png").respond(404)
    results, _ = await check(client, [page(f"{SITE}/", resources=[f"{SITE}/img.png"])])
    link = by_url(results)[f"{SITE}/img.png"]
    assert link.is_broken
    assert link.is_resource
    assert link.found_on == [f"{SITE}/"]


async def test_network_errors(mock_site: respx.MockRouter, client: httpx.AsyncClient) -> None:
    mock_site.head("https://slow.com/").mock(side_effect=httpx.ConnectTimeout("slow"))
    mock_site.head("https://dead.com/").mock(side_effect=httpx.ConnectError("dns"))
    pages = [page(f"{SITE}/", links=["https://slow.com/", "https://dead.com/"])]
    results = by_url((await check(client, pages))[0])
    assert results["https://slow.com/"].error == "timeout"
    assert "ConnectError" in (results["https://dead.com/"].error or "")


async def test_redirects_are_counted(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.head("https://other.com/1").respond(301, headers={"Location": "/2"})
    mock_site.head("https://other.com/2").respond(302, headers={"Location": "/3"})
    mock_site.head("https://other.com/3").respond(200)
    results, _ = await check(client, [page(f"{SITE}/", links=["https://other.com/1"])])
    link = by_url(results)["https://other.com/1"]
    assert link.redirect_count == 2
    assert link.final_url == "https://other.com/3"


async def test_robots_disallowed_internal_links_are_skipped(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    robots = RobotsPolicy.from_text("User-agent: *\nDisallow: /private\n")
    checker = LinkChecker(AuditConfig(start_url=SITE), client, robots)
    pages = [page(f"{SITE}/", links=[f"{SITE}/private"])]
    results = await checker.check(checker.collect_targets(pages), pages)
    assert results == []
    assert checker.blocked_by_robots == [f"{SITE}/private"]
    assert mock_site.calls.call_count == 0


async def test_request_budget_is_respected(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.head(url__startswith="https://other.com/").respond(200)
    links = [f"https://other.com/{i}" for i in range(5)]
    config = AuditConfig(start_url=SITE, max_link_checks=2)
    results, checker = await check(client, [page(f"{SITE}/", links=links)], config)
    assert len(results) == 2
    assert checker.skipped_over_limit == 3
