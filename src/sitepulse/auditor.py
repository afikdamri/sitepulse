"""Orchestrator: wires the pipeline stages together and produces an AuditReport."""

import time
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from typing import Protocol

import httpx

from sitepulse.analyzers import (
    Analyzer,
    AuditData,
    LinkAnalyzer,
    PerformanceAnalyzer,
    SeoAnalyzer,
    compute_performance_stats,
)
from sitepulse.config import AuditConfig
from sitepulse.crawler import Crawler
from sitepulse.link_checker import LinkChecker
from sitepulse.models import AuditReport, LinkResult, PageResult
from sitepulse.rate_limit import MAX_CRAWL_DELAY_S, RateLimiter
from sitepulse.robots import RobotsPolicy
from sitepulse.scoring import score_issues


class AuditError(Exception):
    """The audit could not run at all (e.g. the start URL is unreachable)."""


class AuditProgress(Protocol):
    """Hooks the UI can implement to show live progress. The auditor never prints."""

    def page_done(self, page: PageResult) -> None: ...
    def links_started(self, total: int) -> None: ...
    def link_done(self, link: LinkResult) -> None: ...


class NullProgress:
    def page_done(self, page: PageResult) -> None:
        pass

    def links_started(self, total: int) -> None:
        pass

    def link_done(self, link: LinkResult) -> None:
        pass


def default_analyzers() -> list[Analyzer]:
    return [LinkAnalyzer(), SeoAnalyzer(), PerformanceAnalyzer()]


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
    progress: AuditProgress | None = None,
    analyzers: list[Analyzer] | None = None,
) -> AuditReport:
    started_at = datetime.now(UTC)
    start = time.perf_counter()
    progress = progress or NullProgress()
    notes: list[str] = []

    async with AsyncExitStack() as stack:
        if client is None:  # we own the client only if the caller didn't inject one
            client = await stack.enter_async_context(build_client(config))

        robots = (
            await RobotsPolicy.fetch(client, config.start_url)
            if config.respect_robots
            else RobotsPolicy.allow_all()
        )
        limiter = None
        if robots.crawl_delay:
            delay = min(robots.crawl_delay, MAX_CRAWL_DELAY_S)
            limiter = RateLimiter(delay)
            notes.append(f"robots.txt Crawl-delay honoured: {delay:g}s between requests")

        # 1. Crawl
        crawler = Crawler(config, client, robots, on_page=progress.page_done, limiter=limiter)
        pages = await crawler.crawl()
        if config.start_url in crawler.blocked_by_robots:
            raise AuditError(
                f"{config.start_url} is disallowed by robots.txt (use --ignore-robots to override)"
            )
        if not pages or pages[0].status_code is None:
            reason = pages[0].error if pages else "no response"
            raise AuditError(f"Could not reach {config.start_url}: {reason}")

        # 2. Check links
        checker = LinkChecker(config, client, robots, limiter, on_link=progress.link_done)
        targets = checker.collect_targets(pages)
        progress.links_started(len(targets))
        links = await checker.check(targets, pages)

    # 3. Analyze (pure, no network)
    data = AuditData(config=config, pages=pages, links=links)
    issues = [
        issue for analyzer in analyzers or default_analyzers() for issue in analyzer.analyze(data)
    ]

    # 4. Score: prevalence is measured against the pages we could actually analyze.
    content_pages = [p for p in pages if p.is_html and (p.status_code or 0) < 400]
    result = score_issues(issues, total_pages=len(content_pages))

    # The same URL can be blocked in both phases; count it once.
    skipped_robots = len(set(crawler.blocked_by_robots) | set(checker.blocked_by_robots))
    if skipped_robots:
        notes.append(f"{skipped_robots} URL(s) skipped because of robots.txt")
    if checker.skipped_over_limit:
        notes.append(
            f"{checker.skipped_over_limit} link(s) not checked (limit: {config.max_link_checks})"
        )
    if not config.check_external:
        notes.append("External links were not checked (--no-external)")

    return AuditReport(
        target_url=config.start_url,
        started_at=started_at,
        duration_s=round(time.perf_counter() - start, 2),
        pages=pages,
        links=links,
        issues=issues,
        performance=compute_performance_stats(pages),
        scores=result.scores,
        overall_score=result.overall,
        recommendations=result.recommendations,
        notes=notes,
    )
