"""Command-line interface. Parses options, runs the audit, and hands the report to a reporter."""

import asyncio
import io
import sys
from enum import IntEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
)

from sitepulse import __version__
from sitepulse.auditor import AuditError, run_audit
from sitepulse.config import AuditConfig
from sitepulse.models import AuditReport, LinkResult, PageResult
from sitepulse.reporters import TerminalReporter, report_to_json, write_json

app = typer.Typer(
    help="SitePulse - audit a website's links, SEO and performance.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
# Progress and errors go to stderr, so stdout carries only the report (pipe-friendly).
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
    make_streams_safe(sys.stdout, sys.stderr)


def make_streams_safe(*streams: object) -> None:
    """Never crash on characters the output encoding can't represent.

    On Windows, legacy consoles and the NUL device use cp1252, which has no spinner or box
    characters; replacing them with '?' beats a UnicodeEncodeError halfway through an audit.
    """
    for stream in streams:
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


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
    top: Annotated[int, typer.Option(min=1, help="How many recommendations to show.")] = 10,
    details: Annotated[
        bool, typer.Option("--details", help="Also list every issue and crawled page.")
    ] = False,
    json_path: Annotated[
        Path | None,
        typer.Option("--json", help="Write the full report as JSON. Use '-' for stdout."),
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

    if json_path is not None and str(json_path) == "-":
        sys.stdout.write(report_to_json(report) + "\n")  # JSON only: nothing else on stdout
    else:
        TerminalReporter(console, top=top, details=details).render(report)
        if json_path is not None:
            write_json(report, json_path)
            console.print(f"JSON report written to [bold]{json_path}[/]")

    if fail_under is not None and report.overall_score < fail_under:
        err_console.print(
            f"[bold red]Score {report.overall_score:g} is below --fail-under {fail_under:g}[/]"
        )
        raise typer.Exit(ExitCode.SCORE_BELOW_THRESHOLD)


class _RichProgress:
    """Implements AuditProgress with two live progress bars: crawling, then link checking."""

    def __init__(self, progress: Progress, max_pages: int) -> None:
        self._progress = progress
        self._pages_done = 0
        self._crawl = progress.add_task("Crawling", total=max_pages, current="")
        self._links: TaskID | None = None

    def page_done(self, page: PageResult) -> None:
        self._pages_done += 1
        self._progress.update(self._crawl, advance=1, current=page.url[-60:])

    def links_started(self, total: int) -> None:
        self._progress.update(self._crawl, total=self._pages_done, current="")
        self._links = self._progress.add_task("Checking links", total=total, current="")

    def link_done(self, link: LinkResult) -> None:
        if self._links is not None:
            self._progress.update(self._links, advance=1, current=link.url[-60:])


def _run_with_progress(config: AuditConfig) -> AuditReport:
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description:<15}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[current]}"),
        console=err_console,
        transient=True,  # the bars disappear once the audit is done
    )
    with progress:
        listener = _RichProgress(progress, config.max_pages)
        return asyncio.run(run_audit(config, progress=listener))
