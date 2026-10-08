import pytest

from sitepulse.models import Category, Issue, Severity
from sitepulse.scoring import (
    BASE_IMPACT,
    CATEGORY_WEIGHTS,
    SEVERITY_WEIGHTS,
    rule_penalty,
    score_issues,
)

SITE = "https://example.com"


def issue(
    rule_id: str = "seo.h1.missing",
    severity: Severity = Severity.WARNING,
    category: Category = Category.SEO,
    url: str = f"{SITE}/",
    affected: int = 1,
) -> Issue:
    return Issue(
        rule_id=rule_id,
        category=category,
        severity=severity,
        message="m",
        recommendation=f"fix {rule_id}",
        url=url,
        affected=affected,
    )


def scores_by_category(issues: list[Issue], pages: int) -> dict[Category, float]:
    return {s.category: s.score for s in score_issues(issues, pages).scores}


def test_weights_are_sane() -> None:
    assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(1.0)
    assert set(CATEGORY_WEIGHTS) == set(Category)
    assert SEVERITY_WEIGHTS[Severity.CRITICAL] > SEVERITY_WEIGHTS[Severity.WARNING]
    assert SEVERITY_WEIGHTS[Severity.WARNING] > SEVERITY_WEIGHTS[Severity.INFO]


@pytest.mark.parametrize(
    ("affected", "pages", "fraction_of_weight"),
    [
        (1, 1000, BASE_IMPACT + (1 - BASE_IMPACT) * 0.001),  # rare: ~half the weight
        (50, 100, 0.75),
        (100, 100, 1.0),  # everywhere: full weight
        (500, 100, 1.0),  # prevalence is capped
        (1, 0, 1.0),  # no analyzable pages: treat as site-wide
    ],
)
def test_rule_penalty_scales_with_prevalence(
    affected: int, pages: int, fraction_of_weight: float
) -> None:
    weight = SEVERITY_WEIGHTS[Severity.CRITICAL]
    assert rule_penalty(Severity.CRITICAL, affected, pages) == pytest.approx(
        weight * fraction_of_weight
    )


def test_perfect_site() -> None:
    result = score_issues([], total_pages=10)
    assert [s.score for s in result.scores] == [100, 100, 100]
    assert result.overall == 100
    assert result.recommendations == []


def test_one_broken_link_costs_a_grade_not_the_whole_score() -> None:
    broken = issue("links.internal.broken", Severity.CRITICAL, Category.LINKS)
    result = score_issues([broken], total_pages=50)
    links = next(s for s in result.scores if s.category == Category.LINKS)
    assert links.score == 87.2  # 100 - 25 * (0.5 + 0.5 * 1/50)
    assert links.grade == "B"


def test_a_problem_on_every_page_costs_the_full_weight() -> None:
    issues = [issue("seo.description.missing", url=f"{SITE}/{i}") for i in range(20)]
    assert scores_by_category(issues, 20)[Category.SEO] == 90  # 100 - 10


def test_many_rows_of_one_rule_cannot_sink_a_big_site() -> None:
    issues = [issue("seo.open_graph.missing", Severity.INFO, url=f"{SITE}/{i}") for i in range(500)]
    assert scores_by_category(issues, 500)[Category.SEO] == 98


def test_rules_in_one_category_add_up_and_floor_at_zero() -> None:
    rules = [f"seo.rule{i}" for i in range(6)]
    issues = [issue(rule, Severity.CRITICAL, affected=10) for rule in rules]
    scores = scores_by_category(issues, 10)
    assert scores[Category.SEO] == 0  # 6 x 25 points > 100
    assert scores[Category.LINKS] == 100  # other categories untouched


def test_overall_is_the_weighted_average() -> None:
    issues = [issue("seo.description.missing", affected=10)]  # SEO -> 90
    result = score_issues(issues, total_pages=10)
    assert result.overall == pytest.approx(100 - 10 * CATEGORY_WEIGHTS[Category.SEO])


def test_worst_severity_of_a_rule_counts() -> None:
    issues = [
        issue("perf.page.slow", Severity.WARNING, Category.PERFORMANCE, f"{SITE}/a"),
        issue("perf.page.slow", Severity.CRITICAL, Category.PERFORMANCE, f"{SITE}/b"),
    ]
    [rec] = score_issues(issues, total_pages=4).recommendations
    assert rec.severity == Severity.CRITICAL
    assert rec.occurrences == 2
    assert rec.affected_pages == 2


def test_recommendations_are_ranked_by_impact() -> None:
    issues = [
        issue("seo.open_graph.missing", Severity.INFO, affected=10),
        issue("links.internal.broken", Severity.CRITICAL, Category.LINKS),
        issue("seo.h1.missing", Severity.WARNING, affected=10),
    ]
    recs = score_issues(issues, total_pages=10).recommendations
    assert [(r.rule_id, r.impact) for r in recs] == [
        ("links.internal.broken", 4.8),  # 25 x (0.5 + 0.5 x 1/10) x 0.35
        ("seo.h1.missing", 4.0),  # 10 x 1.0 x 0.40
        ("seo.open_graph.missing", 0.8),  # 2 x 1.0 x 0.40
    ]


def test_recommendation_details() -> None:
    issues = [issue("seo.h1.missing", url=f"{SITE}/{name}") for name in ("a", "b", "a", "c", "d")]
    [rec] = score_issues(issues, total_pages=10).recommendations
    assert rec.title == "Missing <h1> headings"
    assert rec.action == "fix seo.h1.missing"
    assert rec.example_urls == [f"{SITE}/a", f"{SITE}/b", f"{SITE}/c"]  # deduped, max 3
    assert rec.impact == pytest.approx(10 * (0.5 + 0.5 * 5 / 10) * 0.40, abs=0.05)


def test_unknown_rule_falls_back_to_its_id() -> None:
    [rec] = score_issues([issue("custom.rule")], total_pages=1).recommendations
    assert rec.title == "custom.rule"


def test_issue_counts_per_category() -> None:
    issues = [
        issue(severity=Severity.WARNING),
        issue("seo.title.short", Severity.INFO),
        issue("seo.title.long", Severity.INFO),
    ]
    seo = next(s for s in score_issues(issues, 5).scores if s.category == Category.SEO)
    assert seo.issue_counts == {Severity.WARNING: 1, Severity.INFO: 2}
