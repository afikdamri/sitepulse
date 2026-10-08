"""Command-line interface (placeholder until Stage 1)."""

import typer

from sitepulse import __version__

app = typer.Typer(help="SitePulse - audit a website's links, SEO and performance.")


@app.command()
def version() -> None:
    """Print the installed SitePulse version."""
    typer.echo(f"SitePulse {__version__}")


@app.callback()
def main() -> None:
    """SitePulse - audit a website's links, SEO and performance."""
