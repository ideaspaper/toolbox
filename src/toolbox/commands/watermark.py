"""``toolbox watermark``: stamp text or an image onto images and PDFs."""

from pathlib import Path
from typing import Annotated

import typer

from toolbox import watermark


def command(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Images or PDFs to watermark. Each result is saved next to its source "
            "as <name>_watermarked.<ext>.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    text: Annotated[
        str | None,
        typer.Option(
            "--text", "-t", help="Text to repeat diagonally across each page."
        ),
    ] = None,
    image: Annotated[
        Path | None,
        typer.Option(
            "--image",
            "-i",
            help="Image (e.g. a logo) to place in the center of each page.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    opacity: Annotated[
        int,
        typer.Option(
            "--opacity", "-p", min=1, max=100, help="Watermark opacity in percent."
        ),
    ] = 40,
) -> None:
    """Add a text or image watermark to images and PDFs."""
    try:
        stamp = _make_stamp(text, image, opacity / 100)
    except watermark.WatermarkError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    failed = 0
    for path in files:
        try:
            output = watermark.watermark_file(path, stamp)
        except watermark.WatermarkError as exc:
            failed += 1
            typer.secho(f"Error: {path}: {exc}", fg=typer.colors.RED, err=True)
            continue
        typer.echo(f"Saved {output}")

    if failed:
        raise typer.Exit(code=1)


def _make_stamp(
    text: str | None, image: Path | None, opacity: float
) -> watermark.Stamp:
    if text is not None and image is None:
        return watermark.text_stamp(text, opacity)
    if image is not None and text is None:
        return watermark.image_stamp(image, opacity)
    raise typer.BadParameter("use exactly one of --text or --image")
