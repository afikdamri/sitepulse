"""Shared data types that flow through the audit pipeline.

Crawler -> PageResult / LinkResult -> Analyzers -> Issue -> Scorer -> CategoryScore -> AuditReport
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field


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
    size_bytes: int = Field(default=0, ge=0)
    ttfb_ms: float | None = None  # time until response headers arrived
    response_time_ms: float | None = None  # time until the full body was downloaded
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


class CategoryScore(BaseModel):
    category: Category
    score: float = Field(ge=0, le=100)
    issue_counts: dict[Severity, int] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grade(self) -> str:
        return grade_for(self.score)


class AuditReport(BaseModel):
    """Everything a reporter needs to render the final output."""

    target_url: str
    started_at: datetime
    duration_s: float = Field(ge=0)
    pages: list[PageResult] = Field(default_factory=list)
    links: list[LinkResult] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    scores: list[CategoryScore] = Field(default_factory=list)
    overall_score: float = Field(default=0, ge=0, le=100)
    notes: list[str] = Field(default_factory=list)  # informational messages about the run

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_grade(self) -> str:
        return grade_for(self.overall_score)
