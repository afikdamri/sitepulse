"""Audit configuration: user options from the CLI plus tunable thresholds.

Validation lives here (not in the CLI) so there is a single source of truth for what a valid
audit looks like, whatever the entry point is.
"""

import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sitepulse import __version__

DEFAULT_USER_AGENT = f"SitePulse/{__version__} (website audit bot)"

# "mailto:x" or "https://x" have a scheme; "localhost:8000" does not (a digit follows the colon).
_HAS_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:(?!\d)", re.IGNORECASE)


class SeoThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    title_min: int = 30
    title_max: int = 60
    description_min: int = 70
    description_max: int = 160


class PerformanceThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    fast_ms: float = Field(default=200, gt=0)  # at or below: excellent
    slow_ms: float = Field(default=800, gt=0)  # above: flagged as slow
    max_page_kb: float = Field(default=500, gt=0)  # HTML document size

    @model_validator(mode="after")
    def _fast_below_slow(self) -> "PerformanceThresholds":
        if self.fast_ms >= self.slow_ms:
            raise ValueError("fast_ms must be lower than slow_ms")
        return self


class AuditConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_url: str
    max_pages: int = Field(default=50, ge=1, le=10_000)
    max_depth: int = Field(default=3, ge=0, le=20)
    concurrency: int = Field(default=10, ge=1, le=50)
    timeout_s: float = Field(default=10.0, gt=0, le=120)
    user_agent: str = DEFAULT_USER_AGENT
    respect_robots: bool = True
    check_external: bool = True
    max_link_checks: int = Field(default=1000, ge=0, le=100_000)  # extra requests for links
    seo: SeoThresholds = Field(default_factory=SeoThresholds)
    performance: PerformanceThresholds = Field(default_factory=PerformanceThresholds)

    @field_validator("start_url")
    @classmethod
    def _normalize_start_url(cls, value: str) -> str:
        value = value.strip()
        if not _HAS_SCHEME.match(value):
            # allow `sitepulse scan example.com`; local dev servers rarely have TLS
            is_local = value.startswith(("localhost", "127.0.0.1"))
            value = f"{'http' if is_local else 'https'}://{value}"
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https"):
            raise ValueError(f"only http and https URLs are supported, got '{parts.scheme}'")
        if not parts.hostname:
            raise ValueError("URL must include a host name")
        path = parts.path or "/"
        return urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))
