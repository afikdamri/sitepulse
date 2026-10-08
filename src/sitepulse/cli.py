"""Command-line interface. Parses options, builds an AuditConfig, and hands off to the auditor."""

import asyncio
from enum import IntEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from sitepulse import __version__
from sitepulse.auditor import AuditError, run_audit
from sitepulse.config import AuditConfig
from sitepulse.models import AuditReport, PageResult

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

    try:
        report = _run_with_progress(config)
    except AuditError as exc:
        err_console.print(f"[bold red]Audit failed:[/] {exc}")
        raise typer.Exit(ExitCode.AUDIT_FAILED) from None

    _print_pages(report)
    if json_path is not None:
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"JSON report written to [bold]{json_path}[/]")


def _run_with_progress(config: AuditConfig) -> AuditReport:
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Crawling"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[current]}"),
        console=console,
        transient=True,  # the bar disappears once the crawl is done
    )
    with progress:
        task = progress.add_task("crawl", total=config.max_pages, current="")

        def on_page(page: PageResult) -> None:
            progress.update(task, advance=1, current=page.url[-60:])

        return asyncio.run(run_audit(config, on_page=on_page))


def _print_pages(report: AuditReport) -> None:
    table = Table(title=f"Crawled {len(report.pages)} page(s) in {report.duration_s:g}s")
    table.add_column("Status", justify="right")
    table.add_column("TTFB", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Depth", justify="right")
    table.add_column("URL", overflow="fold")
    for page in report.pages:
        table.add_row(
            _status_text(page),
            _ms(page.ttfb_ms),
            _ms(page.response_time_ms),
            str(page.depth),
            page.url,
        )
    console.print(table)
    for note in report.notes:
        console.print(f"[dim]i {note}[/]")


def _status_text(page: PageResult) -> str:
    if page.status_code is None:
        return f"[bold red]{page.error or 'error'}[/]"
    color = "green" if page.status_code < 300 else "yellow" if page.status_code < 400 else "red"
    return f"[{color}]{page.status_code}[/]"


def _ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f} ms"
