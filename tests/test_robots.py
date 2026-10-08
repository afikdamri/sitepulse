import httpx
import respx

from sitepulse.robots import RobotsPolicy

ROBOTS = """
User-agent: *
Disallow: /private

User-agent: SitePulse
Disallow: /no-audit
Crawl-delay: 2
"""


def test_rules_for_our_agent_apply() -> None:
    policy = RobotsPolicy.from_text(ROBOTS)
    assert policy.can_fetch("https://example.com/")
    assert not policy.can_fetch("https://example.com/no-audit/page")
    assert policy.crawl_delay == 2.0


def test_wildcard_rules_apply_when_no_specific_group() -> None:
    policy = RobotsPolicy.from_text("User-agent: *\nDisallow: /private\n")
    assert not policy.can_fetch("https://example.com/private/x")
    assert policy.crawl_delay is None


def test_allow_all() -> None:
    policy = RobotsPolicy.allow_all()
    assert policy.can_fetch("https://example.com/anything")
    assert policy.crawl_delay is None


async def test_fetch_parses_robots_txt(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.get("https://example.com/robots.txt").respond(200, text="User-agent: *\nDisallow: /x")
    policy = await RobotsPolicy.fetch(client, "https://example.com/some/page")
    assert not policy.can_fetch("https://example.com/x")


async def test_missing_robots_txt_allows_everything(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.get("https://example.com/robots.txt").respond(404)
    policy = await RobotsPolicy.fetch(client, "https://example.com/")
    assert policy.can_fetch("https://example.com/x")


async def test_network_error_allows_everything(
    mock_site: respx.MockRouter, client: httpx.AsyncClient
) -> None:
    mock_site.get("https://example.com/robots.txt").mock(side_effect=httpx.ConnectError("boom"))
    policy = await RobotsPolicy.fetch(client, "https://example.com/")
    assert policy.can_fetch("https://example.com/x")
