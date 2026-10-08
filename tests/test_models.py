import json
from datetime import UTC, datetime

import pytest

from sitepulse.models import (
    AuditReport,
    Category,
    CategoryScore,
    LinkResult,
    PageResult,
    Severity,
    grade_for,
)


@pytest.mark.parametrize(
    ("score", "grade"),
    [(100, "A"), (90, "A"), (89.9, "B"), (80, "B"), (70, "C"), (60, "D"), (59.9, "F"), (0, "F")],
)
def test_grade_boundaries(score: float, grade: str) -> None:
    assert grade_for(score) == grade


def test_html_is_excluded_from_json_export() -> None:
    page = PageResult(url="https://example.com/", depth=0, html="<html>huge</html>")
    data = page.model_dump()
    assert "html" not in data
    assert page.html == "<html>huge</html>"  # still available to analyzers


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [("text/html; charset=utf-8", True), ("application/pdf", False), (None, False)],
)
def test_page_is_html(content_type: str | None, expected: bool) -> None:
    assert PageResult(url="u", depth=0, content_type=content_type).is_html is expected


@pytest.mark.parametrize(
    ("status", "error", "broken"),
    [
        (200, None, False),
        (301, None, False),
        (404, None, True),
        (503, None, True),
        (None, "timeout", True),
    ],
)
def test_link_is_broken(status: int | None, error: str | None, broken: bool) -> None:
    link = LinkResult(url="u", is_internal=True, status_code=status, error=error)
    assert link.is_broken is broken


def test_category_score_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        CategoryScore(category=Category.SEO, score=120)


def test_report_round_trips_through_json() -> None:
    report = AuditReport(
        target_url="https://example.com/",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        duration_s=1.5,
        scores=[CategoryScore(category=Category.LINKS, score=85, issue_counts={Severity.INFO: 2})],
        overall_score=85,
    )
    data = json.loads(report.model_dump_json())
    assert data["overall_grade"] == "B"
    assert data["scores"][0]["grade"] == "B"
    assert data["scores"][0]["issue_counts"] == {"info": 2}
