"""Watermark stamps (text or image, opacity baked in) and where to place them.

Placement works in abstract units with the origin at the top-left and y pointing
down, so the same geometry serves images (pixels) and PDF pages (points).
"""

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


class WatermarkError(ValueError):
    """Raised when a file or stamp cannot be watermarked."""


# Text stamps are rendered once at a high resolution and scaled down per target.
BASE_FONT_SIZE = 120
TEXT_COLOR = (80, 80, 80)
TEXT_ANGLE = 30  # degrees, counter-clockwise
TEXT_PADDING = 4  # pixels around the glyphs so anti-aliasing is not clipped by rotation

# Tiled text density, relative to the rendered font size ("em").
FONT_SIZE_RATIO = 0.035  # font size as a fraction of the target's shorter side
MIN_FONT_SIZE = 8.0  # in target units (pixels or points)
COLUMN_GAP_EM = 1.0  # space between repeats on the same line
ROW_GAP_EM = 1.2  # space between lines

IMAGE_FIT_RATIO = 0.8  # an image stamp fills at most 80% of the width or height


@dataclass(frozen=True)
class Stamp:
    """An RGBA stamp. Text stamps are tiled; image stamps are centered once."""

    image: Image.Image
    tiled: bool
    font_size: float = 0.0  # tiled only: font size of `image`, in its pixels
    step_along: float = (
        0.0  # tiled only: distance between repeats along the text direction
    )
    step_across: float = 0.0  # tiled only: distance between lines
    angle: float = 0.0  # tiled only: rotation of the text, degrees counter-clockwise


@dataclass(frozen=True)
class Placement:
    """Stamp size and the top-left corner of every copy, in target units."""

    width: float
    height: float
    positions: list[tuple[float, float]]


def text_stamp(text: str, opacity: float) -> Stamp:
    """Render ``text`` rotated by ``TEXT_ANGLE`` with ``opacity`` (0-1) applied."""
    if not text.strip():
        raise WatermarkError("watermark text must not be empty")
    font = ImageFont.load_default(BASE_FONT_SIZE)
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = measure.multiline_textbbox(
        (0, 0), text, font=font, align="center"
    )
    width, height = math.ceil(right - left), math.ceil(bottom - top)

    canvas = Image.new(
        "RGBA", (width + 2 * TEXT_PADDING, height + 2 * TEXT_PADDING), TEXT_COLOR + (0,)
    )
    ImageDraw.Draw(canvas).multiline_text(
        (TEXT_PADDING - left, TEXT_PADDING - top),
        text,
        font=font,
        fill=TEXT_COLOR + (255,),
        align="center",
    )
    rotated = canvas.rotate(TEXT_ANGLE, resample=Image.Resampling.BICUBIC, expand=True)
    return Stamp(
        image=_with_opacity(rotated, opacity),
        tiled=True,
        font_size=BASE_FONT_SIZE,
        step_along=width + COLUMN_GAP_EM * BASE_FONT_SIZE,
        step_across=height + ROW_GAP_EM * BASE_FONT_SIZE,
        angle=TEXT_ANGLE,
    )


def image_stamp(path: Path, opacity: float) -> Stamp:
    """Load an image (e.g. a logo) as a stamp with ``opacity`` (0-1) applied."""
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise WatermarkError(f"cannot read watermark image {path}: {exc}") from exc
    return Stamp(image=_with_opacity(image, opacity), tiled=False)


def _with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    alpha = image.getchannel("A").point(
        [round(value * opacity) for value in range(256)]
    )
    image.putalpha(alpha)
    return image


def place(stamp: Stamp, area_width: float, area_height: float) -> Placement:
    """Where to draw ``stamp`` on an area of the given size."""
    if stamp.tiled:
        return _tiled_placement(stamp, area_width, area_height)
    return _centered_placement(stamp, area_width, area_height)


def _centered_placement(
    stamp: Stamp, area_width: float, area_height: float
) -> Placement:
    scale = IMAGE_FIT_RATIO * min(
        area_width / stamp.image.width, area_height / stamp.image.height
    )
    width, height = stamp.image.width * scale, stamp.image.height * scale
    return Placement(
        width, height, [((area_width - width) / 2, (area_height - height) / 2)]
    )


def _tiled_placement(stamp: Stamp, area_width: float, area_height: float) -> Placement:
    """A brick pattern of rotated text lines, centered on and covering the area."""
    font_size = max(MIN_FONT_SIZE, FONT_SIZE_RATIO * min(area_width, area_height))
    scale = font_size / stamp.font_size
    width, height = stamp.image.width * scale, stamp.image.height * scale
    along, across = stamp.step_along * scale, stamp.step_across * scale

    # Unit vectors along and across the text, with y pointing down.
    theta = math.radians(stamp.angle)
    along_x, along_y = math.cos(theta), -math.sin(theta)
    across_x, across_y = math.sin(theta), math.cos(theta)

    center_x, center_y = area_width / 2, area_height / 2
    reach = math.hypot(area_width, area_height) / 2 + math.hypot(width, height)
    rows = math.ceil(reach / across)
    columns = math.ceil(reach / along) + 1

    positions = []
    for row in range(-rows, rows + 1):
        shift = along / 2 if row % 2 else 0.0
        for column in range(-columns, columns + 1):
            distance = column * along + shift
            x = center_x + distance * along_x + row * across * across_x - width / 2
            y = center_y + distance * along_y + row * across * across_y - height / 2
            if x < area_width and y < area_height and x + width > 0 and y + height > 0:
                positions.append((x, y))
    return Placement(width, height, positions)
