"""Check every link and resource found during the crawl.

Pages the crawler already fetched are reused for free. Everything else gets a lightweight HEAD
request, falling back to GET because many servers answer HEAD incorrectly (405, 403, even 404).
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from sitepulse.config import AuditConfig
from sitepulse.models import LinkResult, PageResult
from sitepulse.rate_limit import RateLimiter
from sitepulse.robots import RobotsPolicy
from sitepulse.url_utils import is_same_site

LinkCallback = Callable[[LinkResult], None]


@dataclass
class LinkTarget:
    url: str
    is_internal: bool
    is_resource: bool
    found_on: list[str] = field(default_factory=list)


class LinkChecker:
    def __init__(
        self,
        config: AuditConfig,
        client: httpx.AsyncClient,
        robots: RobotsPolicy | None = None,
        limiter: RateLimiter | None = None,
        on_link: LinkCallback | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._robots = robots or RobotsPolicy.allow_all()
        self._limiter = limiter  # applied to our own site only; Crawl-delay is per site
        self._on_link = on_link
        self.blocked_by_robots: list[str] = []
        self.skipped_over_limit = 0

    def collect_targets(self, pages: list[PageResult]) -> list[LinkTarget]:
        """Every unique link/resource URL, with the pages that reference it."""
        targets: dict[str, LinkTarget] = {}
        for page in pages:
            for url, is_resource in [(u, False) for u in page.links] + [
                (u, True) for u in page.resources
            ]:
                target = targets.get(url)
                if target is None:
                    internal = is_same_site(url, self._config.start_url)
                    target = targets[url] = LinkTarget(url, internal, is_resource)
                target.is_resource = target.is_resource and is_resource  # page link wins
                if page.url not in target.found_on:
                    target.found_on.append(page.url)

        if not self._config.check_external:
            return [t for t in targets.values() if t.is_internal]
        return list(targets.values())

    async def check(self, targets: list[LinkTarget], pages: list[PageResult]) -> list[LinkResult]:
        crawled = {page.url: page for page in pages}
        semaphore = asyncio.Semaphore(self._config.concurrency)
        budget = self._config.max_link_checks

        async def check_one(target: LinkTarget) -> LinkResult | None:
            nonlocal budget
            page = crawled.get(target.url)
            if page is not None:
                result = _from_page(target, page)  # already fetched: no request needed
            else:
                if target.is_internal and not self._robots.can_fetch(target.url):
                    self.blocked_by_robots.append(target.url)
                    return None
                if budget <= 0:
                    self.skipped_over_limit += 1
                    return None
                budget -= 1  # reserved synchronously, so no race between tasks
                async with semaphore:
                    result = await self._request(target)
            if self._on_link is not None:
                self._on_link(result)
            return result

        results = await asyncio.gather(*(check_one(target) for target in targets))
        return [result for result in results if result is not None]

    async def _request(self, target: LinkTarget) -> LinkResult:
        result = LinkResult(
            url=target.url,
            is_internal=target.is_internal,
            is_resource=target.is_resource,
            found_on=target.found_on,
        )
        if target.is_internal and self._limiter is not None:
            await self._limiter.wait()
        try:
            response = await self._client.head(target.url)
            if response.status_code >= 400:
                # Retry with GET (body is never downloaded) before declaring the link broken.
                async with self._client.stream("GET", target.url) as response:
                    pass
        except httpx.TimeoutException:
            result.error = "timeout"
            return result
        except httpx.TooManyRedirects:
            result.error = "too many redirects"
            return result
        except httpx.HTTPError as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            return result
        except Exception as exc:  # never let one odd URL abort the whole audit
            result.error = f"internal: {exc!r}"
            return result

        result.status_code = response.status_code
        result.final_url = str(response.url)
        result.redirect_count = len(response.history)
        return result


def _from_page(target: LinkTarget, page: PageResult) -> LinkResult:
    return LinkResult(
        url=target.url,
        is_internal=target.is_internal,
        is_resource=target.is_resource,
        status_code=page.status_code,
        error=page.error,
        final_url=page.final_url,
        redirect_count=len(page.redirect_chain),
        found_on=target.found_on,
    )
