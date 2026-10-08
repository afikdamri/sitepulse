from sitepulse.parsing import extract_links

PAGE = "https://example.com/blog/post"


def test_extracts_and_resolves_anchor_links() -> None:
    html = """
        <a href="/about">About</a>
        <a href="contact">Contact</a>
        <a href="https://other.com/">Other</a>
        <a href="/about">Duplicate</a>
        <a href="mailto:me@example.com">Mail</a>
        <a href="#top">Top</a>
        <a>No href</a>
    """
    links = extract_links(html, PAGE).links
    assert links == [
        "https://example.com/about",
        "https://example.com/blog/contact",
        "https://other.com/",
    ]


def test_extracts_resources() -> None:
    html = """
        <head>
          <link rel="stylesheet" href="/style.css">
          <link rel="icon" href="/favicon.ico">
          <link rel="canonical" href="/canonical">
          <script src="/app.js"></script>
          <script>inline()</script>
        </head>
        <body><img src="img/logo.png"><img alt="no src"></body>
    """
    resources = extract_links(html, PAGE).resources
    assert resources == [
        "https://example.com/app.js",
        "https://example.com/blog/img/logo.png",
        "https://example.com/style.css",
        "https://example.com/favicon.ico",
    ]  # canonical is metadata, not a downloaded resource


def test_base_href_changes_resolution() -> None:
    html = '<head><base href="https://cdn.example.com/root/"></head><a href="page">x</a>'
    assert extract_links(html, PAGE).links == ["https://cdn.example.com/root/page"]


def test_broken_html_does_not_crash() -> None:
    assert extract_links("<a href='/ok'>unclosed <div><p>", PAGE).links == [
        "https://example.com/ok"
    ]
