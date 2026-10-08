"""Command-line interface. Parses options, builds an AuditConfig, and hands off to the auditor."""

from enum import IntEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from sitepulse import __version__
from sitepulse.config import AuditConfig

app = typer.Typer(
    help="SitePulse - audit a website's links, SEO and performance.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


class ExitCode(IntEnum):
    """Process exit codes, so CI pipelines can react to the result."""

    OK = 0
    SCORE_BELOW_THRESHOLD = 1  # audit ran, but the score is under --fail-under
    INVALID_INPUT = 2  # bad URL or option values
    AUDIT_FAILED = 3  # e.g. the start URL is unreachable


@app.callback()
def main() -> None:
    """SitePulse - audit a website's links, SEO and performance."""


@app.command()
def version() -> None:
    """Print the installed SitePulse version."""
    console.print(f"SitePulse {__version__}")


@app.command()
def scan(
    url: Annotated[str, typer.Argument(help="Website to audit, e.g. https://example.com")],
    max_pages: Annotated[int, typer.Option(help="Maximum number of pages to crawl.")] = 50,
    depth: Annotated[int, typer.Option(help="Maximum link depth from the start page.")] = 3,
    concurrency: Annotated[int, typer.Option(help="Parallel requests.")] = 10,
    timeout: Annotated[float, typer.Option(help="Per-request timeout in seconds.")] = 10.0,
    external: Annotated[
        bool, typer.Option("--external/--no-external", help="Also check external links.")
    ] = True,
    robots: Annotated[
        bool, typer.Option("--robots/--ignore-robots", help="Respect robots.txt.")
    ] = True,
    json_path: Annotated[
        Path | None, typer.Option("--json", help="Also write the full report as JSON.")
    ] = None,
    fail_under: Annotated[
        float | None,
        typer.Option(min=0, max=100, help="Exit with code 1 if the overall score is lower."),
    ] = None,
) -> None:
    """Crawl URL and print an audit report."""
    try:
        config = AuditConfig(
            start_url=url,
            max_pages=max_pages,
            max_depth=depth,
            concurrency=concurrency,
            timeout_s=timeout,
            check_external=external,
            respect_robots=robots,
        )
    except ValidationError as exc:
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            message = error["msg"].removeprefix("Value error, ")
            err_console.print(f"[bold red]Invalid {field}:[/] {message}")
        raise typer.Exit(ExitCode.INVALID_INPUT) from None

    _print_config(config)
    console.print("[yellow]Crawler not implemented yet (Stage 2).[/]")


def _print_config(config: AuditConfig) -> None:
    table = Table(title="Audit configuration", show_header=False, title_justify="left")
    table.add_column(style="cyan")
    table.add_column()
    table.add_row("Start URL", config.start_url)
    table.add_row("Max pages", str(config.max_pages))
    table.add_row("Max depth", str(config.max_depth))
    table.add_row("Concurrency", str(config.concurrency))
    table.add_row("Timeout", f"{config.timeout_s:g}s")
    table.add_row("External links", "yes" if config.check_external else "no")
    table.add_row("robots.txt", "respected" if config.respect_robots else "ignored")
    console.print(table)
