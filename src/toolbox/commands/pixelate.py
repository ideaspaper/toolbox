"""``toolbox pixelate``: pixelate whole images or one region of them."""

from pathlib import Path
from typing import Annotated

import typer

from toolbox import pixelate


def command(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Images to pixelate. Each result is saved next to its source "
            "as <name>_pixelated.<ext>.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    block: Annotated[
        int | None,
        typer.Option(
            "--block",
            "-b",
            min=pixelate.MIN_BLOCK_SIZE,
            help="Block size in pixels. Default: about "
            f"{pixelate.BLOCKS_ACROSS} blocks along the longer side.",
        ),
    ] = None,
    region: Annotated[
        str | None,
        typer.Option(
            "--region",
            "-r",
            metavar="X,Y,W,H",
            help="Only pixelate this rectangle, in pixels from the top-left corner "
            "of the image as displayed.",
        ),
    ] = None,
) -> None:
    """Pixelate images, entirely or in one region."""
    try:
        area = pixelate.parse_region(region) if region is not None else None
    except pixelate.PixelateError as exc:
        raise typer.BadParameter(str(exc), param_hint="--region") from exc

    failed = 0
    for path in files:
        try:
            output = pixelate.pixelate_file(path, block, area)
        except pixelate.PixelateError as exc:
            failed += 1
            typer.secho(f"Error: {path}: {exc}", fg=typer.colors.RED, err=True)
            continue
        typer.echo(f"Saved {output}")

    if failed:
        raise typer.Exit(code=1)
