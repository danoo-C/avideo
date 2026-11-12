"""CLI entry point and command registration."""

import typer

from avideo import __version__

app = typer.Typer(
    name="avideo",
    help="Video analysis toolkit · heatmaps, motion, scenes and more.",
    no_args_is_help=True,
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"avideo {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False, "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    """Video analysis toolkit · heatmaps, motion, scenes and more."""


@app.command()
def serve(
    port: int = typer.Option(8765, help="Port to listen on."),
    host: str = typer.Option("127.0.0.1", help="Address to bind to."),
) -> None:
    """Start the local web app (development stub; full behavior in spec-web.md §2)."""
    import uvicorn

    uvicorn.run("avideo.server.app:app", host=host, port=port)


def main() -> None:
    app()
