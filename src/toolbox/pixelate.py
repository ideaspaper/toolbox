"""Pixelate a whole image or one rectangular region of it.

Each block becomes the average color of its pixels: the image is shrunk with box
averaging, enlarged back with nearest-neighbor, and cropped so that every block is a
full square except the partial ones at the right and bottom edges.
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from toolbox import imaging

OUTPUT_SUFFIX = "_pixelated"
BLOCKS_ACROSS = 64  # automatic block size: this many blocks along the longer side
MIN_BLOCK_SIZE = 2


class PixelateError(ValueError):
    """Raised when an image or region cannot be pixelated."""


@dataclass(frozen=True)
class Region:
    """A rectangle in pixels, measured on the image as it is displayed (upright)."""

    x: int
    y: int
    width: int
    height: int


def parse_region(text: str) -> Region:
    """Parse ``X,Y,WIDTH,HEIGHT`` (whole pixels)."""
    parts = [part.strip() for part in text.split(",")]
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError:
        raise PixelateError(
            f"invalid region {text!r}: use X,Y,WIDTH,HEIGHT in whole pixels"
        ) from None
    if x < 0 or y < 0:
        raise PixelateError("region X and Y must not be negative")
    if width < 1 or height < 1:
        raise PixelateError("region WIDTH and HEIGHT must be at least 1")
    return Region(x, y, width, height)


def auto_block_size(image_size: tuple[int, int]) -> int:
    """About ``BLOCKS_ACROSS`` blocks along the image's longer side."""
    return max(MIN_BLOCK_SIZE, round(max(image_size) / BLOCKS_ACROSS))


def pixelate(
    image: Image.Image, block_size: int | None = None, region: Region | None = None
) -> Image.Image:
    """Return a pixelated copy of an RGBA ``image``.

    ``block_size`` defaults to ``auto_block_size`` of the whole image, so a region is
    pixelated as coarsely as the whole image would be. A region reaching past the
    image edge is clipped to it.
    """
    if block_size is None:
        block_size = auto_block_size(image.size)
    if block_size < MIN_BLOCK_SIZE:
        raise PixelateError(f"block size must be at least {MIN_BLOCK_SIZE}")

    result = image.copy()
    if region is None:
        return _pixelate_all(result, block_size)

    box = (
        region.x,
        region.y,
        min(region.x + region.width, image.width),
        min(region.y + region.height, image.height),
    )
    if box[0] >= image.width or box[1] >= image.height:
        raise PixelateError(
            f"region starts outside the {image.width}x{image.height} image"
        )
    result.paste(_pixelate_all(result.crop(box), block_size), box[:2])
    return result


def _pixelate_all(image: Image.Image, block_size: int) -> Image.Image:
    # Premultiplied alpha ("RGBa") stops transparent pixels from darkening the
    # average color of semi-transparent blocks.
    small = image.convert("RGBa").reduce(block_size)
    enlarged = small.resize(
        (small.width * block_size, small.height * block_size),
        Image.Resampling.NEAREST,
    )
    return enlarged.crop((0, 0, image.width, image.height)).convert("RGBA")


def pixelate_file(
    path: Path, block_size: int | None = None, region: Region | None = None
) -> Path:
    """Pixelate ``path`` and write the result next to it; return the output path."""
    try:
        image, source = imaging.load(path)
    except imaging.ImageError as exc:
        raise PixelateError(str(exc)) from exc
    data, extension = imaging.encode(pixelate(image, block_size, region), source)

    output = path.with_name(f"{path.stem}{OUTPUT_SUFFIX}{extension}")
    try:
        output.write_bytes(data)
    except OSError as exc:
        raise PixelateError(f"cannot write {output}: {exc.strerror or exc}") from exc
    return output
