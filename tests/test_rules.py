"""Meta-test: every rule_id an analyzer can emit must have a human-readable title."""

import re
from pathlib import Path

from sitepulse.rules import RULE_TITLES

ANALYZERS = Path(__file__).parents[1] / "src" / "sitepulse" / "analyzers"
# Literal rule ids like "seo.title.missing" (f-string ids are listed explicitly below).
RULE_ID = re.compile(r'"((?:links|seo|perf)\.[a-z0-9_]+(?:\.[a-z0-9_]+)*)"')
DYNAMIC_RULE_IDS = {"seo.duplicate.title", "seo.duplicate.description"}


def rule_ids_in_source() -> set[str]:
    found: set[str] = set()
    for path in ANALYZERS.glob("*.py"):
        found.update(RULE_ID.findall(path.read_text(encoding="utf-8")))
    return found


def test_scan_finds_the_rules() -> None:
    assert len(rule_ids_in_source()) >= 30  # guards against a broken regex passing silently


def test_every_rule_has_a_title() -> None:
    missing = (rule_ids_in_source() | DYNAMIC_RULE_IDS) - RULE_TITLES.keys()
    assert not missing, f"add titles to sitepulse/rules.py for: {sorted(missing)}"


def test_no_stale_titles() -> None:
    stale = RULE_TITLES.keys() - (rule_ids_in_source() | DYNAMIC_RULE_IDS)
    assert not stale, f"rules.py has titles for rules no analyzer emits: {sorted(stale)}"
