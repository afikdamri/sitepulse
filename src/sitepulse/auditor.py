"""Orchestrator: wires the pipeline stages together and produces an AuditReport."""

import time
from contextlib import AsyncExitStack
from datetime import UTC, datetime

import httpx

from sitepulse.config import AuditConfig
from sitepulse.crawler import Crawler, PageCallback
from sitepulse.models import AuditReport
from sitepulse.robots import RobotsPolicy


class AuditError(Exception):
    """The audit could not run at all (e.g. the start URL is unreachable)."""


def build_client(config: AuditConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=config.timeout_s,
        follow_redirects=True,
        headers={"User-Agent": config.user_agent},
        limits=httpx.Limits(max_connections=config.concurrency * 2),
    )


async def run_audit(
    config: AuditConfig,
    *,
    client: httpx.AsyncClient | None = None,
    on_page: PageCallback | None = None,
) -> AuditReport:
    started_at = datetime.now(UTC)
    start = time.perf_counter()

    async with AsyncExitStack() as stack:
        if client is None:  # we own the client only if the caller didn't inject one
            client = await stack.enter_async_context(build_client(config))

        robots = (
            await RobotsPolicy.fetch(client, config.start_url)
            if config.respect_robots
            else RobotsPolicy.allow_all()
        )
        crawler = Crawler(config, client, robots, on_page)
        pages = await crawler.crawl()

    if config.start_url in crawler.blocked_by_robots:
        raise AuditError(
            f"{config.start_url} is disallowed by robots.txt (use --ignore-robots to override)"
        )
    if not pages or pages[0].status_code is None:
        reason = pages[0].error if pages else "no response"
        raise AuditError(f"Could not reach {config.start_url}: {reason}")

    notes: list[str] = []
    if crawler.crawl_delay_s:
        notes.append(
            f"robots.txt Crawl-delay honoured: {crawler.crawl_delay_s:g}s between requests"
        )
    if crawler.blocked_by_robots:
        notes.append(f"{len(crawler.blocked_by_robots)} URL(s) skipped because of robots.txt")

    return AuditReport(
        target_url=config.start_url,
        started_at=started_at,
        duration_s=round(time.perf_counter() - start, 2),
        pages=pages,
        notes=notes,
    )
