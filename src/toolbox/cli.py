"""Root CLI application. Each feature in ``toolbox.commands`` is registered here."""

from typing import Annotated

import typer

from toolbox import __version__
from toolbox.commands import pixel, pixelate, qr, sprite, watermark

app = typer.Typer(
    help="A personal toolbox of small command-line utilities.",
    no_args_is_help=True,
    add_completion=False,
)
app.command(name="qr")(qr.command)
app.command(name="watermark")(watermark.command)
app.command(name="pixelate")(pixelate.command)
app.command(name="sprite")(sprite.command)
app.add_typer(pixel.app, name="pixel")


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-V", help="Show the version and exit.")
    ] = False,
) -> None:
    """A personal toolbox of small command-line utilities."""
    if version:
        typer.echo(f"toolbox {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
