# SitePulse

> A fast, async command-line tool that crawls a website and audits **broken links**, **SEO tags**
> and **server response times** — then prints a beautiful, scored report with actionable fixes.

🚧 Work in progress.

## Planned features
- Async BFS crawler (same-origin, respects `robots.txt`, configurable depth/concurrency)
- Broken link detection (internal + external, redirect chains)
- SEO analysis (title, meta description, H1, canonical, Open Graph, image alt, ...)
- Performance metrics (TTFB, p50/p95 response times, page size, compression)
- Scores per category (0-100, A-F) and prioritized recommendations
- Rich terminal report + JSON export + CI-friendly exit codes

## Development
```bash
uv sync
uv run sitepulse --help
uv run pytest
```

## License
MIT
