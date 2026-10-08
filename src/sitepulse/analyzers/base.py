"""The contract every analyzer implements.

Analyzers are pure functions of the collected data: no network, no printing. That makes each
one trivial to unit-test with hand-built PageResult/LinkResult objects.
"""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from sitepulse.config import AuditConfig
from sitepulse.models import Category, Issue, LinkResult, PageResult


@dataclass(frozen=True)
class AuditData:
    """Everything collected during the audit, handed to each analyzer."""

    config: AuditConfig
    pages: list[PageResult]
    links: list[LinkResult]


class Analyzer(Protocol):
    category: Category

    def analyze(self, data: AuditData) -> list[Issue]: ...


def short_url(url: str) -> str:
    """Path + query, for compact messages about pages on the audited site."""
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "") or "/"


def describe_pages(urls: list[str], limit: int = 3) -> str:
    """'/a, /b and 4 more' - keeps messages short when a link appears on many pages."""
    shown = ", ".join(short_url(url) for url in urls[:limit])
    extra = len(urls) - limit
    return f"{shown} and {extra} more" if extra > 0 else shown
