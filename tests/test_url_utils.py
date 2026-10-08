import pytest

from sitepulse.url_utils import is_same_site, normalize_url, resolve_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTP://Example.COM", "http://example.com/"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://example.com:8443/a", "https://example.com:8443/a"),
        ("https://example.com/a#section", "https://example.com/a"),
        ("https://example.com/a?x=1&y=2", "https://example.com/a?x=1&y=2"),
        ("https://example.com/about/", "https://example.com/about/"),  # trailing slash kept
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["ftp://example.com/", "https://", "http://host:abc/", "nope"])
def test_normalize_rejects_non_crawlable(raw: str) -> None:
    assert normalize_url(raw) is None


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/about", "https://example.com/about"),
        ("contact", "https://example.com/blog/contact"),
        ("../up", "https://example.com/up"),
        ("//cdn.example.org/x.js", "https://cdn.example.org/x.js"),
        ("https://other.com/#frag", "https://other.com/"),
        ("#top", None),
        ("", None),
        ("mailto:me@example.com", None),
        ("tel:+972500000000", None),
        ("javascript:void(0)", None),
    ],
)
def test_resolve_url(href: str, expected: str | None) -> None:
    assert resolve_url("https://example.com/blog/post", href) == expected


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("https://example.com/a", "https://example.com/b", True),
        ("https://example.com/", "https://www.example.com/x", True),
        ("http://example.com/", "https://example.com/", True),
        ("https://example.com/", "https://blog.example.com/", False),
        ("http://localhost:8000/", "http://localhost:9000/", False),
        ("https://example.com/", "https://other.com/", False),
    ],
)
def test_is_same_site(a: str, b: str, same: bool) -> None:
    assert is_same_site(a, b) is same
