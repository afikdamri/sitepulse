"""Regenerate the README screenshot: run a real audit and export the terminal report as SVG.

Usage:
    uv run python scripts/screenshot.py [URL] [--max-pages N]
"""

import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.terminal_theme import MONOKAI

from sitepulse.auditor import run_audit
from sitepulse.config import AuditConfig
from sitepulse.reporters import TerminalReporter

OUTPUT = Path(__file__).parents[1] / "docs" / "report.svg"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="https://books.toscrape.com")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()

    config = AuditConfig(start_url=args.url, max_pages=args.max_pages, max_depth=2)
    report = asyncio.run(run_audit(config))

    console = Console(record=True, width=110, force_terminal=True, color_system="truecolor")
    TerminalReporter(console, top=args.top).render(report)
    OUTPUT.parent.mkdir(exist_ok=True)
    console.save_svg(str(OUTPUT), title=f"sitepulse scan {args.url}", theme=MONOKAI)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
