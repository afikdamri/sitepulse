import pytest

from sitepulse.analyzers import AuditData, PerformanceAnalyzer, compute_performance_stats
from sitepulse.analyzers.performance import measurable_pages, percentile
from sitepulse.config import AuditConfig, PerformanceThresholds
from sitepulse.models import Category, Issue, PageResult, Severity

SITE = "https://example.com"


def perf_page(
    path: str = "/",
    ttfb: float = 100,
    size: int = 20_000,
    encoding: str | None = "gzip",
    status: int = 200,
) -> PageResult:
    return PageResult(
        url=f"{SITE}{path}",
        depth=0,
        status_code=status,
        content_type="text/html; charset=utf-8",
        content_encoding=encoding,
        ttfb_ms=ttfb,
        response_time_ms=ttfb + 20,
        size_bytes=size,
        transfer_bytes=size // 5 if encoding else size,
    )


def analyze(pages: list[PageResult], limits: PerformanceThresholds | None = None) -> list[Issue]:
    config = AuditConfig(start_url=SITE, performance=limits or PerformanceThresholds())
    return PerformanceAnalyzer().analyze(AuditData(config=config, pages=pages, links=[]))


def rule_ids(issues: list[Issue]) -> list[str]:
    return sorted(issue.rule_id for issue in issues)


# ---- percentile -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [
        ([10, 20, 30, 40], 50, 25.0),  # between the two middle values
        ([10, 20, 30], 50, 20.0),
        ([40, 10, 30, 20], 50, 25.0),  # input order doesn't matter
        ([10, 20, 30, 40], 0, 10.0),
        ([10, 20, 30, 40], 100, 40.0),
        ([7], 95, 7.0),
        (list(range(1, 101)), 95, 95.05),
    ],
)
def test_percentile(values: list[float], p: float, expected: float) -> None:
    assert percentile(values, p) == pytest.approx(expected)


@pytest.mark.parametrize(("values", "p"), [([], 50), ([1.0], -1), ([1.0], 101)])
def test_percentile_rejects_bad_input(values: list[float], p: float) -> None:
    with pytest.raises(ValueError):
        percentile(values, p)


def test_average_is_misleading_but_median_is_not() -> None:
    times = [100.0] * 9 + [5000.0]
    assert sum(times) / len(times) == 590  # describes no real page
    assert percentile(times, 50) == 100  # the typical page
    assert percentile(times, 95) > 2000  # the slow tail is still visible


# ---- statistics -------------------------------------------------------------------------------


def test_only_successful_html_pages_are_measured() -> None:
    pdf = perf_page("/file.pdf")
    pdf.content_type = "application/pdf"
    failed = PageResult(url=f"{SITE}/down", depth=1, error="timeout")
    pages = [perf_page(), perf_page("/404", status=404), pdf, failed]
    assert [p.url for p in measurable_pages(pages)] == [f"{SITE}/"]


def test_compute_performance_stats() -> None:
    pages = [
        perf_page("/a", ttfb=100, size=10_240),
        perf_page("/b", ttfb=300, size=20_480, encoding=None),
        perf_page("/c", ttfb=200, size=30_720),
    ]
    stats = compute_performance_stats(pages)
    assert stats is not None
    assert stats.pages_measured == 3
    assert stats.server_time.avg_ms == 200
    assert stats.server_time.p50_ms == 200
    assert stats.server_time.max_ms == 300
    assert stats.avg_connect_ms is None  # no page opened a new connection
    assert stats.response_time.p50_ms == 220
    assert stats.total_html_kb == 60
    assert stats.avg_html_kb == 20
    assert stats.total_transfer_kb == 2 + 20 + 6  # only /b was sent uncompressed
    assert stats.compressed_pages == 2
    assert stats.slowest_pages == [f"{SITE}/b", f"{SITE}/c", f"{SITE}/a"]


def test_no_measurable_pages_means_no_stats() -> None:
    assert compute_performance_stats([PageResult(url=SITE, depth=0, error="timeout")]) is None


# ---- rules ------------------------------------------------------------------------------------


def test_fast_compressed_site_has_no_issues() -> None:
    assert analyze([perf_page(f"/{i}", ttfb=80 + i) for i in range(10)]) == []


def test_no_pages_no_issues() -> None:
    assert analyze([]) == []


@pytest.mark.parametrize(("ttfb", "severity"), [(900, Severity.WARNING), (1700, Severity.CRITICAL)])
def test_slow_page(ttfb: float, severity: Severity) -> None:
    pages = [perf_page("/", ttfb=100), perf_page("/slow", ttfb=ttfb)]
    [issue] = [i for i in analyze(pages) if i.rule_id == "perf.page.slow"]
    assert issue.severity == severity
    assert issue.url == f"{SITE}/slow"
    assert issue.category == Category.PERFORMANCE
    assert f"{ttfb:.0f} ms" in issue.message


def test_large_html() -> None:
    issues = analyze([perf_page(size=600 * 1024)])
    assert rule_ids(issues) == ["perf.html.large"]
    assert "600 KB" in issues[0].message


def test_missing_compression_is_one_site_wide_issue() -> None:
    pages = [
        perf_page("/a", encoding=None),
        perf_page("/b", encoding=None),
        perf_page("/c"),
        perf_page("/tiny", encoding=None, size=300),  # too small to matter
    ]
    [issue] = analyze(pages)
    assert issue.rule_id == "perf.compression.missing"
    assert issue.message.startswith("2 of 4 HTML pages")


def test_high_median_ttfb() -> None:
    issues = analyze([perf_page(f"/{i}", ttfb=450) for i in range(3)])
    assert rule_ids(issues) == ["perf.ttfb.median_high"]
    assert issues[0].severity == Severity.INFO


def test_erratic_response_times() -> None:
    pages = [perf_page(f"/{i}", ttfb=100) for i in range(9)] + [perf_page("/x", ttfb=2000)]
    assert rule_ids(analyze(pages)) == ["perf.page.slow", "perf.ttfb.inconsistent"]


def test_thresholds_come_from_config() -> None:
    strict = PerformanceThresholds(fast_ms=50, slow_ms=90, max_page_kb=10)
    issues = analyze([perf_page(ttfb=100)], strict)
    assert rule_ids(issues) == ["perf.html.large", "perf.page.slow", "perf.ttfb.median_high"]


def test_connection_setup_is_not_blamed_on_the_server() -> None:
    # A fresh TCP+TLS connection made this page's TTFB 1500 ms, but the server answered in 150.
    cold = perf_page("/cold", ttfb=1500)
    cold.connect_ms = 1350
    pages = [perf_page("/warm", ttfb=140), cold]

    assert cold.server_ms == 150
    assert analyze(pages) == []  # no false "slow page" alarm
    stats = compute_performance_stats(pages)
    assert stats is not None
    assert stats.server_time.max_ms == 150
    assert stats.avg_connect_ms == 1350
