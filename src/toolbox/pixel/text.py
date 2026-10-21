"""Text views of a sprite: a grid with coordinates, and a colored terminal preview."""

from toolbox.pixel.model import DEFAULT_DURATION, TRANSPARENT, Grid, Sprite

RESET = "\033[0m"


def palette_legend(sprite: Sprite) -> str:
    entries = [f"{TRANSPARENT} transparent"]
    entries += [f"{key} {color}" for key, color in sprite.palette.items()]
    legend = "palette: " + " | ".join(entries)
    if sprite.layered:
        legend += "\nlayers (bottom to top): " + ", ".join(sprite.layers)
    if sprite.anchor is not None:
        legend += f"\nanchor: {sprite.anchor[0]},{sprite.anchor[1]}"
    return legend


def grid_with_coordinates(grid: Grid) -> str:
    """The frame with column numbers on top and row numbers on the left.

    Column numbers are stacked digits (tens above units) so every column stays one
    character wide and lines up with the pixels below it.
    """
    width, height = len(grid[0]), len(grid)
    margin = len(str(height - 1)) + 1
    digits = len(str(width - 1))
    header = []
    for place in range(digits - 1, -1, -1):
        labels = "".join(str(x // 10**place % 10) for x in range(width))
        if place:  # blank the leading zeros of the tens/hundreds rows
            labels = "".join(
                label if x >= 10**place else " " for x, label in enumerate(labels)
            )
        header.append(" " * margin + labels)
    rows = [f"{y:>{margin - 1}} {''.join(row)}" for y, row in enumerate(grid)]
    return "\n".join(header + rows)


def colored_preview(sprite: Sprite, grid: Grid) -> str:
    """Truecolor half-block preview: one character shows two stacked pixels."""
    colors = {key: color.rgba for key, color in sprite.palette.items()}
    lines = []
    for y in range(0, sprite.height, 2):
        top = grid[y]
        bottom = grid[y + 1] if y + 1 < sprite.height else [TRANSPARENT] * sprite.width
        cells = []
        for upper, lower in zip(top, bottom, strict=True):
            cells.append(_half_block(colors.get(upper), colors.get(lower)))
        lines.append("".join(cells) + RESET)
    return "\n".join(lines)


def _half_block(upper, lower) -> str:
    if upper is None and lower is None:
        return f"{RESET} "
    if upper is None:
        return f"{RESET}\033[38;2;{lower[0]};{lower[1]};{lower[2]}m▄"
    code = f"\033[38;2;{upper[0]};{upper[1]};{upper[2]}m"
    if lower is not None:
        code += f"\033[48;2;{lower[0]};{lower[1]};{lower[2]}m"
    else:
        code = RESET + code
    return f"{code}▀"


def frame_title(
    sprite: Sprite, animation: str, index: int, layer: str | None = None
) -> str:
    """Which frame this is; ``layer`` None on a layered sprite means all layers."""
    frames = sprite.animations[animation]
    title = f"animation {animation} | frame {index} of 0-{len(frames) - 1}"
    if sprite.layered:
        title += f" | layer {layer}" if layer else " | all layers"
    if frames[index].duration != DEFAULT_DURATION:
        title += f" | {frames[index].duration} ms"
    return (
        f"{title} | {sprite.width}x{sprite.height}, x 0-{sprite.width - 1}, "
        f"y 0-{sprite.height - 1}"
    )
