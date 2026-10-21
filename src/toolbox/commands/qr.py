"""``toolbox qr``: generate a QR code image or print one to the terminal."""

import sys
from pathlib import Path
from typing import Annotated

import typer

from toolbox import qr


def command(
    data: Annotated[
        str | None,
        typer.Argument(
            help="Text or URL to encode. Use '-' or omit it to read from stdin."
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Image file to write. The format follows the .png/.svg extension. "
            "Without it, the QR code is printed to the terminal.",
            dir_okay=False,
        ),
    ] = None,
    image_format: Annotated[
        qr.ImageFormat | None,
        typer.Option(
            "--format", "-f", help="Image format, overriding the file extension."
        ),
    ] = None,
    error_correction: Annotated[
        qr.ErrorCorrection,
        typer.Option(
            "--error",
            "-e",
            help="Error correction level (L ~7%, M ~15%, Q ~25%, H ~30%).",
        ),
    ] = qr.ErrorCorrection.M,
    foreground: Annotated[
        str, typer.Option("--fg", help="Module color: a common color name or #RRGGBB.")
    ] = "black",
    background: Annotated[
        str,
        typer.Option("--bg", help="Background color: a common color name or #RRGGBB."),
    ] = "white",
    scale: Annotated[
        int, typer.Option("--scale", "-s", min=1, max=50, help="Pixels per module.")
    ] = 10,
    border: Annotated[
        int,
        typer.Option(
            "--border",
            "-b",
            min=0,
            max=20,
            help="Quiet zone width in modules (4 is the spec minimum).",
        ),
    ] = 4,
) -> None:
    """Generate a QR code."""
    text = _read_data(data)
    if image_format is None:
        image_format = _format_from_path(output) if output else qr.ImageFormat.PNG

    options = qr.QROptions(
        error_correction=error_correction,
        foreground=foreground,
        background=background,
        scale=scale,
        border=border,
        image_format=image_format,
    )

    try:
        if output is None:
            typer.echo(qr.render_terminal(text, options), nl=False)
            return
        output.write_bytes(qr.generate(text, options))
    except qr.QRError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        typer.secho(
            f"Error: cannot write {output}: {exc.strerror}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc

    typer.echo(f"Saved {output}")


def _read_data(data: str | None) -> str:
    """Return ``data``, or read it from stdin when it is missing or ``-``."""
    if data is not None and data != "-":
        return data
    if sys.stdin.isatty():
        raise typer.BadParameter("provide DATA or pipe it via stdin", param_hint="DATA")
    return sys.stdin.read().rstrip("\n")


def _format_from_path(path: Path) -> qr.ImageFormat:
    suffix = path.suffix.lower().lstrip(".")
    try:
        return qr.ImageFormat(suffix)
    except ValueError:
        raise typer.BadParameter(
            f"cannot infer the image format from {path.name!r}; "
            "use a .png/.svg extension or --format",
            param_hint="--output",
        ) from None
