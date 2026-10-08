import io
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sitepulse import __version__
from sitepulse.cli import ExitCode, app, make_streams_safe

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == ExitCode.OK
    assert __version__ in result.output


def test_unencodable_output_is_replaced_not_fatal() -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")  # like the Windows NUL device
    make_streams_safe(stream, "not a stream")
    stream.write("⠋ Crawling ┌─┐")
    stream.flush()
    assert buffer.getvalue() == b"? Crawling ???"


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


@pytest.mark.parametrize(
    ("threshold", "expected_exit"),
    [("0", ExitCode.OK), ("100", ExitCode.SCORE_BELOW_THRESHOLD)],
)
def test_fail_under_sets_exit_code(
    mock_site: respx.MockRouter, html: Callable[..., str], threshold: str, expected_exit: int
) -> None:
    mock_site.get("https://example.com/robots.txt").respond(404)
    # The test page lacks a description, lang, viewport... so it can't score 100.
    mock_site.get("https://example.com/").respond(200, html=html())
    result = runner.invoke(app, ["scan", "example.com", "--fail-under", threshold])
    assert result.exit_code == expected_exit, result.output
    assert "Overall:" in result.output


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


def test_json_to_stdout_is_pure_json(mock_site: respx.MockRouter, html: Callable[..., str]) -> None:
    mock_site.get("https://example.com/robots.txt").respond(404)
    mock_site.get("https://example.com/").respond(200, html=html())
    result = runner.invoke(app, ["scan", "example.com", "--json", "-"])
    assert result.exit_code == ExitCode.OK
    data = json.loads(result.stdout)  # would fail if the terminal report leaked into stdout
    assert data["target_url"] == "https://example.com/"
    assert data["tool_version"] == __version__


def test_details_and_top_options(mock_site: respx.MockRouter, html: Callable[..., str]) -> None:
    mock_site.get("https://example.com/robots.txt").respond(404)
    mock_site.get("https://example.com/").respond(200, html=html())
    brief = runner.invoke(app, ["scan", "example.com", "--top", "1"])
    full = runner.invoke(app, ["scan", "example.com", "--details"])
    assert "Top 1 recommendations" in brief.output
    assert "more - run with --details" in brief.output
    assert "All issues" not in brief.output
    assert "All issues" in full.output
    assert "Crawled pages" in full.output
