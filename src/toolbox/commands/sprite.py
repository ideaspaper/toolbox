"""``toolbox sprite``: turn images into small pixel-art sprites."""

from pathlib import Path
from typing import Annotated

import typer

from toolbox import sprite


def command(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Images to turn into sprites. Each result is saved next to its source "
            "as <name>_sprite.png.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    size: Annotated[
        int,
        typer.Option(
            "--size",
            "-s",
            min=1,
            max=sprite.MAX_SIZE,
            help="Sprite size in pixels along the longer side.",
        ),
    ] = sprite.DEFAULT_SIZE,
    colors: Annotated[
        int,
        typer.Option(
            "--colors",
            "-c",
            min=sprite.MIN_COLORS,
            max=sprite.MAX_COLORS,
            help="Maximum number of colors in the sprite's palette.",
        ),
    ] = sprite.DEFAULT_COLORS,
) -> None:
    """Turn images into small pixel-art sprites (PNG with hard transparency)."""
    failed = 0
    for path in files:
        try:
            output = sprite.sprite_file(path, size, colors)
        except sprite.SpriteError as exc:
            failed += 1
            typer.secho(f"Error: {path}: {exc}", fg=typer.colors.RED, err=True)
            continue
        typer.echo(f"Saved {output}")

    if failed:
        raise typer.Exit(code=1)
