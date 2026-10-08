import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sitepulse import __version__
from sitepulse.cli import ExitCode, app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == ExitCode.OK
    assert __version__ in result.output


def test_no_arguments_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "scan" in result.output


def test_scan_prints_crawled_pages_and_writes_json(
    mock_site: respx.MockRouter, html: Callable[..., str], tmp_path: Path
) -> None:
    mock_site.get("https://example.com/robots.txt").respond(404)
    mock_site.get("https://example.com/").respond(200, html=html("/about"))
    mock_site.get("https://example.com/about").respond(404, html=html())
    report_file = tmp_path / "report.json"

    result = runner.invoke(app, ["scan", "Example.com", "--json", str(report_file)])

    assert result.exit_code == ExitCode.OK, result.output
    assert "https://example.com/about" in result.output
    assert "404" in result.output
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert [page["url"] for page in data["pages"]] == [
        "https://example.com/",
        "https://example.com/about",
    ]


def test_scan_unreachable_site_exits_with_code_3(mock_site: respx.MockRouter) -> None:
    mock_site.get(url__startswith="https://down.example").mock(
        side_effect=httpx.ConnectError("dns failure")
    )
    result = runner.invoke(app, ["scan", "down.example"])
    assert result.exit_code == ExitCode.AUDIT_FAILED
    assert "Could not reach" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["scan", "ftp://example.com"],
        ["scan", "https://"],
        ["scan", "example.com", "--max-pages", "0"],
        ["scan", "example.com", "--concurrency", "500"],
    ],
)
def test_scan_invalid_input_exits_with_code_2(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == ExitCode.INVALID_INPUT


def test_fail_under_out_of_range_is_rejected() -> None:
    result = runner.invoke(app, ["scan", "example.com", "--fail-under", "150"])
    assert result.exit_code == ExitCode.INVALID_INPUT  # Typer/Click usage errors also exit 2
