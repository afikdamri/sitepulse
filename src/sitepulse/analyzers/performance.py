"""Server performance: response-time statistics and rules for slow, heavy or uncompressed pages.

Why percentiles instead of the average: response times are skewed. Nine pages at 100 ms and one
at 5 s average 590 ms - a number that describes *no* page. The median (p50) shows the typical
experience and p95 shows the slow tail that real visitors still hit.
"""

import math

from sitepulse.analyzers.base import AuditData, describe_pages, short_url
from sitepulse.config import PerformanceThresholds
from sitepulse.models import (
    Category,
    Issue,
    PageResult,
    PerformanceStats,
    Severity,
    TimingStats,
)

MIN_COMPRESSIBLE_BYTES = 1024  # compressing tiny responses saves nothing
SLOWEST_PAGES_SHOWN = 5
INCONSISTENCY_RATIO = 3  # p95 this many times above p50 means erratic performance


def percentile(values: list[float], p: float) -> float:
    """The value below which `p` percent of `values` fall (linear interpolation).

    percentile([10, 20, 30, 40], 50) == 25.0
    """
    if not values:
        raise ValueError("percentile of an empty list")
    if not 0 <= p <= 100:
        raise ValueError("p must be between 0 and 100")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p / 100  # fractional index into the sorted list
    low, high = math.floor(rank), math.ceil(rank)
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def measurable_pages(pages: list[PageResult]) -> list[PageResult]:
    """Successful HTML pages with timings - errors and files would distort the numbers."""
    return [
        page
        for page in pages
        if page.is_html
        and page.status_code is not None
        and page.status_code < 400
        and page.server_ms is not None
        and page.response_time_ms is not None
    ]


def compute_performance_stats(pages: list[PageResult]) -> PerformanceStats | None:
    measured = measurable_pages(pages)
    if not measured:
        return None
    server = [p.server_ms for p in measured if p.server_ms is not None]
    total = [p.response_time_ms for p in measured if p.response_time_ms is not None]
    connects = [p.connect_ms for p in measured if p.connect_ms > 0]
    sizes_kb = [p.size_bytes / 1024 for p in measured]
    slowest = sorted(measured, key=lambda p: p.server_ms or 0, reverse=True)
    return PerformanceStats(
        pages_measured=len(measured),
        server_time=_timing_stats(server),
        response_time=_timing_stats(total),
        avg_connect_ms=round(sum(connects) / len(connects), 1) if connects else None,
        avg_html_kb=round(sum(sizes_kb) / len(sizes_kb), 1),
        total_html_kb=round(sum(sizes_kb), 1),
        total_transfer_kb=round(sum(p.transfer_bytes for p in measured) / 1024, 1),
        compressed_pages=sum(1 for p in measured if p.content_encoding),
        slowest_pages=[p.url for p in slowest[:SLOWEST_PAGES_SHOWN]],
    )


def _timing_stats(values: list[float]) -> TimingStats:
    return TimingStats(
        avg_ms=round(sum(values) / len(values), 1),
        p50_ms=round(percentile(values, 50), 1),
        p95_ms=round(percentile(values, 95), 1),
        max_ms=round(max(values), 1),
    )


class PerformanceAnalyzer:
    category = Category.PERFORMANCE

    def analyze(self, data: AuditData) -> list[Issue]:
        limits = data.config.performance
        pages = measurable_pages(data.pages)
        stats = compute_performance_stats(data.pages)
        if stats is None:
            return []

        issues = [issue for page in pages for issue in self._page_issues(page, limits)]
        issues.extend(self._site_issues(pages, stats, limits))
        return issues

    def _page_issues(self, page: PageResult, limits: PerformanceThresholds) -> list[Issue]:
        issues: list[Issue] = []
        server_ms = page.server_ms or 0
        if server_ms > limits.slow_ms:
            very_slow = server_ms > 2 * limits.slow_ms
            issues.append(
                self._issue(
                    "perf.page.slow",
                    Severity.CRITICAL if very_slow else Severity.WARNING,
                    f"Server took {server_ms:.0f} ms to respond to {short_url(page.url)} "
                    f"(slow above {limits.slow_ms:.0f} ms)",
                    "Profile this page on the server: slow database queries, missing caching "
                    "and heavy server-side rendering are the usual causes. A CDN or page "
                    "cache can also help.",
                    page.url,
                )
            )

        size_kb = page.size_bytes / 1024
        if size_kb > limits.max_page_kb:
            issues.append(
                self._issue(
                    "perf.html.large",
                    Severity.WARNING,
                    f"HTML document is {size_kb:.0f} KB (max {limits.max_page_kb:.0f} KB): "
                    f"{short_url(page.url)}",
                    "Move inline scripts/styles/SVGs into cacheable files, paginate long "
                    "lists, and remove unused markup.",
                    page.url,
                )
            )
        return issues

    def _site_issues(
        self, pages: list[PageResult], stats: PerformanceStats, limits: PerformanceThresholds
    ) -> list[Issue]:
        issues: list[Issue] = []
        first_url = pages[0].url

        uncompressed = [
            p.url
            for p in pages
            if not p.content_encoding and p.size_bytes >= MIN_COMPRESSIBLE_BYTES
        ]
        if uncompressed:
            issues.append(
                self._issue(
                    "perf.compression.missing",
                    Severity.WARNING,
                    f"{len(uncompressed)} of {len(pages)} HTML pages are served without "
                    f"compression: {describe_pages(uncompressed)}",
                    "Enable gzip or Brotli compression on the web server; it typically "
                    "shrinks HTML by 70-90%.",
                    uncompressed[0],
                    affected=len(uncompressed),
                )
            )

        if stats.server_time.p50_ms > limits.fast_ms:
            issues.append(
                self._issue(
                    "perf.ttfb.median_high",
                    Severity.INFO,
                    f"Typical server response time (median) is {stats.server_time.p50_ms:.0f} ms; "
                    f"aim for under {limits.fast_ms:.0f} ms",
                    "Add server-side caching or a CDN close to your visitors to cut the "
                    "baseline response time.",
                    first_url,
                    affected=len(pages),  # a property of the whole server
                )
            )

        p50, p95 = stats.server_time.p50_ms, stats.server_time.p95_ms
        if len(pages) >= 5 and p95 > limits.slow_ms and p95 > INCONSISTENCY_RATIO * p50:
            issues.append(
                self._issue(
                    "perf.ttfb.inconsistent",
                    Severity.INFO,
                    f"Response times are erratic: median {p50:.0f} ms but p95 {p95:.0f} ms",
                    "Look for pages that skip the cache or hit expensive queries; the slow tail "
                    "is what frustrated visitors remember.",
                    first_url,
                    affected=len(pages),
                )
            )
        return issues

    def _issue(
        self,
        rule_id: str,
        severity: Severity,
        message: str,
        recommendation: str,
        url: str,
        affected: int = 1,
    ) -> Issue:
        return Issue(
            rule_id=rule_id,
            category=self.category,
            severity=severity,
            message=message,
            recommendation=recommendation,
            url=url,
            affected=affected,
        )
