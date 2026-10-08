"""Async breadth-first crawler.

A fixed pool of `concurrency` worker tasks pulls (url, depth) jobs from a shared queue. Because
jobs are processed roughly in the order they were discovered, pages closer to the start URL are
crawled first (BFS), so `max_pages` keeps the most important pages.
"""

import asyncio
import time
from collections.abc import Callable

import httpx

from sitepulse.config import AuditConfig
from sitepulse.models import PageResult
from sitepulse.parsing import extract_links
from sitepulse.rate_limit import RateLimiter
from sitepulse.robots import RobotsPolicy
from sitepulse.url_utils import is_same_site, normalize_url

MAX_HTML_BYTES = 5 * 1024 * 1024  # stop reading absurdly large documents

PageCallback = Callable[[PageResult], None]


class Crawler:
    def __init__(
        self,
        config: AuditConfig,
        client: httpx.AsyncClient,
        robots: RobotsPolicy | None = None,
        on_page: PageCallback | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._robots = robots or RobotsPolicy.allow_all()
        self._on_page = on_page
        self._limiter = limiter

        self._seen: dict[str, int] = {}  # url -> discovery order (also our "visited" set)
        self._redirect_targets: set[str] = set()  # already fetched under another URL
        self._results: list[PageResult] = []
        self.blocked_by_robots: list[str] = []

    async def crawl(self) -> list[PageResult]:
        queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self._schedule(queue, self._config.start_url, depth=0)

        workers = [
            asyncio.create_task(self._worker(queue)) for _ in range(self._config.concurrency)
        ]
        await queue.join()  # returns once every queued job called task_done()
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        # Workers finish in arbitrary order; report pages in BFS discovery order.
        return sorted(self._results, key=lambda page: self._seen.get(page.url, 0))

    def _schedule(self, queue: asyncio.Queue[tuple[str, int]], url: str, depth: int) -> None:
        if url in self._seen or url in self._redirect_targets:
            return
        if len(self._seen) >= self._config.max_pages:
            return
        if not self._robots.can_fetch(url):
            if url not in self.blocked_by_robots:
                self.blocked_by_robots.append(url)
            return
        self._seen[url] = len(self._seen)
        queue.put_nowait((url, depth))

    async def _worker(self, queue: asyncio.Queue[tuple[str, int]]) -> None:
        while True:
            url, depth = await queue.get()
            try:
                page = await self._fetch(url, depth)
                self._results.append(page)
                if self._on_page is not None:
                    self._on_page(page)
                self._schedule_children(queue, page)
            except Exception as exc:  # one bad page must never kill the whole crawl
                self._results.append(PageResult(url=url, depth=depth, error=f"internal: {exc!r}"))
            finally:
                queue.task_done()

    def _schedule_children(self, queue: asyncio.Queue[tuple[str, int]], page: PageResult) -> None:
        if page.final_url and page.final_url != page.url:
            # Remember the redirect target so we never fetch it a second time.
            self._redirect_targets.add(page.final_url)
        if page.depth >= self._config.max_depth:
            return
        for link in page.links:
            if is_same_site(link, self._config.start_url):
                self._schedule(queue, link, page.depth + 1)

    async def _fetch(self, url: str, depth: int) -> PageResult:
        if self._limiter is not None:
            await self._limiter.wait()

        start = time.perf_counter()
        try:
            async with self._client.stream("GET", url) as response:
                ttfb_ms = (time.perf_counter() - start) * 1000  # headers have arrived
                content_type = response.headers.get("content-type")
                is_html = content_type is not None and "text/html" in content_type
                body = await _read_limited(response) if is_html else b""
                total_ms = (time.perf_counter() - start) * 1000
        except httpx.TimeoutException:
            return PageResult(url=url, depth=depth, error="timeout")
        except httpx.TooManyRedirects:
            return PageResult(url=url, depth=depth, error="too many redirects")
        except httpx.HTTPError as exc:
            return PageResult(url=url, depth=depth, error=f"{type(exc).__name__}: {exc}")

        final_url = normalize_url(str(response.url)) or str(response.url)
        page = PageResult(
            url=url,
            final_url=final_url,
            depth=depth,
            status_code=response.status_code,
            content_type=content_type,
            content_encoding=response.headers.get("content-encoding"),
            size_bytes=len(body) if is_html else _content_length(response),
            ttfb_ms=round(ttfb_ms, 1),
            response_time_ms=round(total_ms, 1),
            redirect_chain=[str(r.url) for r in response.history],
        )
        # Only parse successful HTML on this site: error pages and other sites are not crawled.
        if is_html and response.status_code < 400 and is_same_site(final_url, url):
            page.html = body.decode(response.encoding or "utf-8", errors="replace")
            extracted = extract_links(page.html, final_url)
            page.links = extracted.links
            page.resources = extracted.resources
        return page


async def _read_limited(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_HTML_BYTES:
            break
    return b"".join(chunks)[:MAX_HTML_BYTES]


def _content_length(response: httpx.Response) -> int:
    try:
        return int(response.headers.get("content-length", 0))
    except ValueError:
        return 0
