"""Convert sprites to images (single frames or sprite sheets) and images to sprites."""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PIL import Image

from toolbox.pixel.model import (
    KEY_CHARACTERS,
    MAIN_LAYER,
    MAX_SIZE,
    TRANSPARENT,
    Color,
    Frame,
    Grid,
    PixelError,
    Sprite,
)

MAX_SCALE = 64
CLEAR = (0, 0, 0, 0)


class Layout(StrEnum):
    HORIZONTAL = "horizontal"  # every frame in one row, in file order
    GRID = "grid"  # one row per animation, its frames left to right


@dataclass(frozen=True)
class Sheet:
    image: Image.Image
    # Where each frame landed, in output pixels, and how long it shows:
    # {animation: [{x, y, w, h, duration}, ...]}
    frames: dict[str, list[dict[str, int]]]


def _grid_image(sprite: Sprite, grid: Grid) -> Image.Image:
    image = Image.new("RGBA", (sprite.width, sprite.height), CLEAR)
    colors = {key: color.rgba for key, color in sprite.palette.items()}
    image.putdata(
        [colors.get(key, CLEAR) for row in grid for key in row]  # "." -> clear
    )
    return image


def frame_image(sprite: Sprite, frame: Frame | Grid, scale: int = 1) -> Image.Image:
    """One frame as an image; a Frame's layers are stacked bottom to top."""
    _check_scale(scale)
    if isinstance(frame, Frame):
        image = Image.new("RGBA", (sprite.width, sprite.height), CLEAR)
        for name in sprite.layers:  # real alpha blending for partly clear colors
            image = Image.alpha_composite(
                image, _grid_image(sprite, frame.layers[name])
            )
    else:
        image = _grid_image(sprite, frame)
    return _scaled(image, scale)


def _scaled(image: Image.Image, scale: int) -> Image.Image:
    if scale == 1:
        return image
    size = (image.width * scale, image.height * scale)
    return image.resize(size, Image.Resampling.NEAREST)


def onion_image(
    sprite: Sprite, animation: str, index: int, scale: int = 1, opacity: float = 0.3
) -> Image.Image:
    """The frame drawn over a faint copy of the frame before it, to check motion."""
    frames = sprite.animations[animation]
    image = frame_image(sprite, frames[index])
    if len(frames) > 1:
        ghost = frame_image(sprite, frames[index - 1])  # frame 0 shows the last one
        alpha = ghost.getchannel("A").point(lambda value: int(value * opacity))
        ghost.putalpha(alpha)
        image = Image.alpha_composite(ghost, image)
    return _scaled(image, scale)


def save_animation(sprite: Sprite, animation: str, path: Path, scale: int = 1) -> None:
    """Write one animation as a looping GIF, timed by each frame's duration."""
    _check_scale(scale)
    frames = sprite.animations[animation]
    images = [frame_image(sprite, frame, scale) for frame in frames]
    images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=[frame.duration for frame in frames],
        loop=0,
        disposal=2,  # clear between frames so transparent areas stay clear
    )


def render_sheet(
    sprite: Sprite,
    layout: Layout = Layout.HORIZONTAL,
    scale: int = 1,
    animations: list[str] | None = None,
) -> Sheet:
    """All frames of ``animations`` (default: every animation) in one image."""
    _check_scale(scale)
    names = animations or list(sprite.animations)
    frame_width, frame_height = sprite.width * scale, sprite.height * scale

    cells: dict[str, list[tuple[int, int]]] = {}
    column = 0
    for row, name in enumerate(names):
        count = len(sprite.animations[name])
        if layout is Layout.GRID:
            cells[name] = [(index, row) for index in range(count)]
        else:
            cells[name] = [(column + index, 0) for index in range(count)]
            column += count

    columns = max(cell[0] for positions in cells.values() for cell in positions) + 1
    rows = max(cell[1] for positions in cells.values() for cell in positions) + 1
    sheet = Image.new("RGBA", (columns * frame_width, rows * frame_height), CLEAR)
    frames: dict[str, list[dict[str, int]]] = {}
    for name, positions in cells.items():
        frames[name] = []
        for frame, (col, row) in zip(sprite.animations[name], positions, strict=True):
            x, y = col * frame_width, row * frame_height
            sheet.paste(frame_image(sprite, frame, scale), (x, y))
            frames[name].append(
                {
                    "x": x,
                    "y": y,
                    "w": frame_width,
                    "h": frame_height,
                    "duration": frame.duration,
                }
            )
    return Sheet(sheet, frames)


def _check_scale(scale: int) -> None:
    if not 1 <= scale <= MAX_SCALE:
        raise PixelError(f"scale must be between 1 and {MAX_SCALE}")


def import_image(image: Image.Image, animation: str = "idle") -> Sprite:
    """Make a one-frame sprite from an image with few enough colors.

    Fully transparent pixels become ``.``; partly transparent colors keep their
    alpha as ``#RRGGBBAA``. The most common color gets the first key (``a``).
    """
    if image.width > MAX_SIZE or image.height > MAX_SIZE:
        raise PixelError(
            f"the image is {image.width}x{image.height}; sprites are at most "
            f"{MAX_SIZE}x{MAX_SIZE}. Shrink it first, e.g. `toolbox sprite -s 32`"
        )
    rgba = image.convert("RGBA")
    data = rgba.tobytes()  # R, G, B, A bytes for each pixel in turn
    pixels = [
        CLEAR if data[i + 3] == 0 else (data[i], data[i + 1], data[i + 2], data[i + 3])
        for i in range(0, len(data), 4)
    ]
    counts = Counter(pixel for pixel in pixels if pixel != CLEAR)
    if len(counts) > len(KEY_CHARACTERS):
        raise PixelError(
            f"the image has {len(counts)} colors; sprites support at most "
            f"{len(KEY_CHARACTERS)}. Reduce them first, e.g. `toolbox sprite -c 32`"
        )

    keys = {
        color: KEY_CHARACTERS[index]
        for index, (color, _) in enumerate(counts.most_common())
    }
    sprite = Sprite(width=rgba.width, height=rgba.height)
    for (red, green, blue, alpha), key in keys.items():
        hex_color = f"#{red:02X}{green:02X}{blue:02X}"
        sprite.palette[key] = Color(
            hex_color if alpha == 255 else f"{hex_color}{alpha:02X}"
        )
    keyed = [keys.get(pixel, TRANSPARENT) for pixel in pixels]
    grid = [keyed[y * rgba.width : (y + 1) * rgba.width] for y in range(rgba.height)]
    sprite.animations[animation] = [Frame({MAIN_LAYER: grid})]
    return sprite
