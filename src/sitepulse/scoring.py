"""Turn issues into category scores, an overall score and prioritized recommendations.

The model, in one sentence: every rule that fires costs its category points according to
how severe it is and how much of the site it affects.

    penalty(rule) = SEVERITY_WEIGHT x (BASE_IMPACT + (1 - BASE_IMPACT) x prevalence)
    prevalence    = min(1, pages affected by the rule / pages analyzed)
    category      = max(0, 100 - sum of its rules' penalties)
    overall       = weighted average of the categories

BASE_IMPACT means any occurrence costs at least half the weight: one broken link on a
500-page site is still a real problem. Prevalence scales the rest: missing descriptions on
every page cost the full weight, on one page only half. Many rows from the *same* rule can
never sink a score on their own, which keeps big sites from being punished for their size.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sitepulse.models import Category, CategoryScore, Issue, Recommendation, Severity
from sitepulse.rules import rule_title

SEVERITY_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 25,
    Severity.WARNING: 10,
    Severity.INFO: 2,
}
CATEGORY_WEIGHTS: dict[Category, float] = {
    Category.LINKS: 0.35,
    Category.SEO: 0.40,
    Category.PERFORMANCE: 0.25,
}
BASE_IMPACT = 0.5
EXAMPLE_URLS = 3
_SEVERITY_ORDER = list(Severity)  # CRITICAL, WARNING, INFO


@dataclass(frozen=True)
class ScoreResult:
    scores: list[CategoryScore]
    overall: float
    recommendations: list[Recommendation]


def rule_penalty(severity: Severity, affected_pages: int, total_pages: int) -> float:
    prevalence = min(1.0, affected_pages / max(1, total_pages))
    return SEVERITY_WEIGHTS[severity] * (BASE_IMPACT + (1 - BASE_IMPACT) * prevalence)


def score_issues(issues: list[Issue], total_pages: int) -> ScoreResult:
    by_rule: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        by_rule[issue.rule_id].append(issue)

    penalties: dict[Category, float] = defaultdict(float)
    recommendations: list[Recommendation] = []
    for rule_id, rule_issues in by_rule.items():
        first = rule_issues[0]
        severity = min((i.severity for i in rule_issues), key=_SEVERITY_ORDER.index)
        affected = sum(i.affected for i in rule_issues)
        penalty = rule_penalty(severity, affected, total_pages)
        penalties[first.category] += penalty

        example_urls = list(dict.fromkeys(i.url for i in rule_issues if i.url))[:EXAMPLE_URLS]
        recommendations.append(
            Recommendation(
                rule_id=rule_id,
                title=rule_title(rule_id),
                category=first.category,
                severity=severity,
                action=first.recommendation,
                occurrences=len(rule_issues),
                affected_pages=min(affected, max(1, total_pages)),
                impact=round(penalty * CATEGORY_WEIGHTS[first.category], 1),
                example_urls=example_urls,
            )
        )

    scores = [
        CategoryScore(
            category=category,
            score=round(max(0.0, 100 - penalties[category]), 1),
            issue_counts=_count_by_severity(i for i in issues if i.category == category),
        )
        for category in Category
    ]
    overall = round(sum(s.score * CATEGORY_WEIGHTS[s.category] for s in scores), 1)
    recommendations.sort(key=lambda r: (-r.impact, _SEVERITY_ORDER.index(r.severity), r.rule_id))
    return ScoreResult(scores=scores, overall=overall, recommendations=recommendations)


def _count_by_severity(issues: Iterable[Issue]) -> dict[Severity, int]:
    counts: dict[Severity, int] = {}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts
