"""URL helpers: resolving, normalizing and comparing URLs.

Normalization is what keeps the crawler from fetching the same page twice under different
spellings (`HTTP://Example.com:80/a#top` and `http://example.com/a` are the same resource).
"""

from urllib.parse import urljoin, urlsplit, urlunsplit

CRAWLABLE_SCHEMES = ("http", "https")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str) -> str | None:
    """Return a canonical form of an http(s) URL, or None if it is not crawlable."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port  # raises ValueError for garbage like "host:abc"
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in CRAWLABLE_SCHEMES or not parts.hostname:
        return None

    host = parts.hostname  # already lower-cased by urlsplit
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        host = f"{host}:{port}"
    # Trailing slashes are kept on purpose: /about and /about/ may be different resources.
    path = parts.path or "/"
    return urlunsplit((scheme, host, path, parts.query, ""))  # fragment dropped


def resolve_url(base_url: str, href: str) -> str | None:
    """Resolve an href found on `base_url` to an absolute, normalized URL.

    Returns None for links that point nowhere crawlable (mailto:, tel:, javascript:, #top, ...).
    """
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    return normalize_url(urljoin(base_url, href))


def site_key(url: str) -> str:
    """Identify the website a URL belongs to.

    `www.` and the scheme are ignored, because sites commonly redirect example.com to
    www.example.com and http to https; treating those as different sites would make every
    link look external.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    port = parts.port
    if port is not None and port != _DEFAULT_PORTS.get(parts.scheme):
        host = f"{host}:{port}"
    return host


def is_same_site(url: str, other: str) -> bool:
    return site_key(url) == site_key(other)
