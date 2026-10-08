import pytest
from pydantic import ValidationError

from sitepulse.config import AuditConfig, PerformanceThresholds


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com/"),
        ("  https://Example.COM  ", "https://example.com/"),
        ("http://example.com/blog?page=2#comments", "http://example.com/blog?page=2"),
        ("https://example.com:8080/a", "https://example.com:8080/a"),
        ("localhost:8000", "http://localhost:8000/"),
        ("127.0.0.1/docs", "http://127.0.0.1/docs"),
    ],
)
def test_start_url_is_normalized(raw: str, expected: str) -> None:
    assert AuditConfig(start_url=raw).start_url == expected


@pytest.mark.parametrize(
    "raw", ["ftp://example.com", "mailto:me@example.com", "javascript:alert(1)", "https://"]
)
def test_invalid_start_url_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        AuditConfig(start_url=raw)


@pytest.mark.parametrize(
    "overrides",
    [{"max_pages": 0}, {"max_depth": -1}, {"concurrency": 0}, {"timeout_s": 0}],
)
def test_out_of_range_options_are_rejected(overrides: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        AuditConfig(start_url="example.com", **overrides)


def test_config_is_immutable() -> None:
    config = AuditConfig(start_url="example.com")
    with pytest.raises(ValidationError):
        config.max_pages = 999  # type: ignore[misc]


def test_fast_threshold_must_be_below_slow() -> None:
    with pytest.raises(ValidationError):
        PerformanceThresholds(fast_ms=900, slow_ms=800)
