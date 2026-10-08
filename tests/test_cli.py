import pytest
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


def test_scan_valid_url_prints_normalized_config() -> None:
    result = runner.invoke(app, ["scan", "Example.com", "--max-pages", "5", "--no-external"])
    assert result.exit_code == ExitCode.OK
    assert "https://example.com/" in result.output
    assert "5" in result.output


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
