from collections.abc import AsyncIterator, Callable, Iterator

import httpx
import pytest
import respx

SITE = "https://example.com"


def make_html(*links: str, head: str = "<title>Test page</title>", body: str = "") -> str:
    anchors = "".join(f'<a href="{link}">{link}</a>' for link in links)
    return f"<html><head>{head}</head><body>{anchors}{body}</body></html>"


@pytest.fixture
def html() -> Callable[..., str]:
    """Build a small HTML page linking to the given hrefs."""
    return make_html


@pytest.fixture
def mock_site() -> Iterator[respx.MockRouter]:
    """Intercept every httpx request; unmocked URLs fail loudly instead of hitting the network."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        yield http_client
