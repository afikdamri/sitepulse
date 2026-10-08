"""Shared data types that flow through the audit pipeline.

Crawler -> PageResult / LinkResult -> Analyzers -> Issue -> Scorer -> CategoryScore -> AuditReport
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from sitepulse import __version__


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Category(StrEnum):
    LINKS = "links"
    SEO = "seo"
    PERFORMANCE = "performance"


def grade_for(score: float) -> str:
    """Map a 0-100 score to a letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class PageResult(BaseModel):
    """Raw data the crawler collected for a single page. No judgement here, only facts."""

    url: str
    final_url: str | None = None  # after redirects
    depth: int = Field(ge=0)
    status_code: int | None = None  # None when the request failed (timeout, DNS, ...)
    error: str | None = None
    content_type: str | None = None
    content_encoding: str | None = None
    size_bytes: int = Field(default=0, ge=0)  # decoded HTML size
    transfer_bytes: int = Field(default=0, ge=0)  # bytes over the wire (after compression)
    ttfb_ms: float | None = None  # time until response headers arrived
    response_time_ms: float | None = None  # time until the full body was downloaded
    connect_ms: float = Field(default=0, ge=0)  # new TCP+TLS setup; 0 if connection reused

    @computed_field  # type: ignore[prop-decorator]
    @property
    def server_ms(self) -> float | None:
        """Server response time: TTFB without connection setup - what the server controls."""
        if self.ttfb_ms is None:
            return None
        return round(max(self.ttfb_ms - self.connect_ms, 0), 1)

    redirect_chain: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)  # absolute <a href> targets
    resources: list[str] = Field(default_factory=list)  # absolute <img>/<script>/<link> targets
    # The HTML is needed by analyzers but is far too large for reports.
    html: str | None = Field(default=None, exclude=True, repr=False)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_html(self) -> bool:
        return self.content_type is not None and "text/html" in self.content_type


class LinkResult(BaseModel):
    """Result of checking one unique link target (internal or external)."""

    url: str
    is_internal: bool
    is_resource: bool = False  # image/script/stylesheet rather than a navigable <a> link
    status_code: int | None = None
    error: str | None = None
    final_url: str | None = None  # after redirects
    redirect_count: int = Field(default=0, ge=0)
    found_on: list[str] = Field(default_factory=list)  # pages that link here

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_broken(self) -> bool:
        return self.error is not None or (self.status_code is not None and self.status_code >= 400)


class Issue(BaseModel):
    """A single problem found by an analyzer, with a concrete fix."""

    rule_id: str  # stable machine id, e.g. "seo.title.missing"
    category: Category
    severity: Severity
    message: str
    recommendation: str
    url: str | None = None  # None for site-wide issues
    affected: int = Field(default=1, ge=1)  # pages this issue touches; drives its score impact


class CategoryScore(BaseModel):
    category: Category
    score: float = Field(ge=0, le=100)
    issue_counts: dict[Severity, int] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grade(self) -> str:
        return grade_for(self.score)


class TimingStats(BaseModel):
    avg_ms: float
    p50_ms: float  # median: the typical page
    p95_ms: float  # 95% of pages are at least this fast: the "bad day" experience
    max_ms: float


class PerformanceStats(BaseModel):
    """Site-wide performance summary, computed once so reporters only display it."""

    pages_measured: int
    server_time: TimingStats  # TTFB minus connection setup: what the server itself controls
    response_time: TimingStats  # full download, as a visitor experiences it
    avg_connect_ms: float | None = None  # cost of a new TCP+TLS connection, when one was opened
    avg_html_kb: float
    total_html_kb: float
    total_transfer_kb: float
    compressed_pages: int
    slowest_pages: list[str] = Field(default_factory=list)  # URLs, slowest TTFB first


class Recommendation(BaseModel):
    """One rule's issues rolled up into a single prioritized action item."""

    rule_id: str
    title: str
    category: Category
    severity: Severity  # the worst severity among this rule's issues
    action: str  # what to do about it
    occurrences: int  # how many issues this rule produced
    affected_pages: int
    impact: float  # overall-score points regained by fixing every occurrence
    example_urls: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """Everything a reporter needs to render the final output."""

    tool_version: str = __version__  # lets JSON consumers know which SitePulse wrote it
    target_url: str
    started_at: datetime
    duration_s: float = Field(ge=0)
    pages: list[PageResult] = Field(default_factory=list)
    links: list[LinkResult] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    performance: PerformanceStats | None = None  # None when no page could be measured
    scores: list[CategoryScore] = Field(default_factory=list)
    overall_score: float = Field(default=0, ge=0, le=100)
    recommendations: list[Recommendation] = Field(default_factory=list)  # most impactful first
    notes: list[str] = Field(default_factory=list)  # informational messages about the run

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_grade(self) -> str:
        return grade_for(self.overall_score)
