"""Turn an image into a small pixel-art sprite.

The image is reduced to a limited palette (chosen from its opaque pixels) and shrunk
so that each sprite pixel covers a cell of the source. A cell is opaque when at least
``MIN_OPAQUE_SHARE`` of it is opaque, and then takes the most common palette color
among its opaque pixels. Unlike averaging, this never invents in-between colors, so
the sprite stays crisp and uses exactly the palette.
"""

from pathlib import Path

from PIL import Image, ImageChops

from toolbox import imaging

OUTPUT_SUFFIX = "_sprite"
OUTPUT_EXTENSION = ".png"  # sprites need exact colors and transparency: always PNG
ALPHA_THRESHOLD = 128  # source pixels at least this opaque count as opaque
# A cell needs this share of opaque pixels to be drawn. Below one half, so thin
# outlines at the silhouette's edge survive instead of becoming transparent.
MIN_OPAQUE_SHARE = 1 / 3
MAX_SIZE = 512
MIN_COLORS = 2
MAX_COLORS = 255  # one of the 256 palette slots marks transparent pixels
DEFAULT_SIZE = 32
DEFAULT_COLORS = 32


class SpriteError(ValueError):
    """Raised when an image cannot be turned into a sprite."""


def sprite_size(image_size: tuple[int, int], size: int) -> tuple[int, int]:
    """Scale ``image_size`` so its longer side is ``size``, keeping the aspect ratio."""
    width, height = image_size
    scale = size / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def make_sprite(
    image: Image.Image, size: int = DEFAULT_SIZE, colors: int = DEFAULT_COLORS
) -> Image.Image:
    """Return an RGBA sprite of ``image`` with ``size`` pixels on its longer side."""
    if not 1 <= size <= MAX_SIZE:
        raise SpriteError(f"size must be between 1 and {MAX_SIZE}")
    if size > max(image.size):
        raise SpriteError(
            f"size {size} is larger than the {image.width}x{image.height} image; "
            "sprites can only be made smaller"
        )
    if not MIN_COLORS <= colors <= MAX_COLORS:
        raise SpriteError(f"colors must be between {MIN_COLORS} and {MAX_COLORS}")

    opaque = image.getchannel("A").point(
        [0] * ALPHA_THRESHOLD + [255] * (256 - ALPHA_THRESHOLD)
    )
    if opaque.getbbox() is None:
        raise SpriteError("the image is fully transparent")

    indexed, palette = _quantize(image, opaque, colors)
    transparent_index = len(palette)
    # Mark transparent pixels with an index of their own so cells can count them.
    indexed.paste(transparent_index, mask=ImageChops.invert(opaque))

    width, height = sprite_size(image.size, size)
    sprite = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = sprite.load()
    assert pixels is not None
    for y in range(height):
        top, bottom = y * image.height // height, (y + 1) * image.height // height
        for x in range(width):
            left, right = x * image.width // width, (x + 1) * image.width // width
            index = _cell_index(
                indexed.crop((left, top, right, bottom)), transparent_index
            )
            if index is not None:
                pixels[x, y] = palette[index] + (255,)
    return sprite


def _quantize(
    image: Image.Image, opaque: Image.Image, colors: int
) -> tuple[Image.Image, list[tuple[int, int, int]]]:
    """Map ``image`` to at most ``colors`` colors chosen from its opaque pixels only."""
    rgb = image.convert("RGB")
    # Transparent pixels often hold arbitrary colors; keep them out of the palette.
    opaque_pixels = [
        color
        for color, keep in zip(
            rgb.get_flattened_data(), opaque.get_flattened_data(), strict=True
        )
        if keep
    ]
    sample = Image.new("RGB", (len(opaque_pixels), 1))
    sample.putdata(opaque_pixels)
    palette_image = sample.quantize(
        colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
    )
    used = len(palette_image.getcolors() or [])
    flat = (palette_image.getpalette() or [])[: used * 3]
    palette = [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat), 3)]

    indexed = rgb.quantize(palette=palette_image, dither=Image.Dither.NONE)
    return indexed, palette


def _cell_index(cell: Image.Image, transparent_index: int) -> int | None:
    """Most common opaque palette index in ``cell``; None if it is too transparent."""
    counts = {
        index: count
        for count, index in cell.getcolors(256) or []
        if isinstance(index, int)  # always true for a palette ("P") image
    }
    transparent = counts.pop(transparent_index, 0)
    opaque = sum(counts.values())
    if opaque == 0 or opaque < MIN_OPAQUE_SHARE * (opaque + transparent):
        return None
    # Ties go to the lower palette index, so results are repeatable.
    return max(counts, key=lambda index: (counts[index], -index))


def sprite_file(
    path: Path, size: int = DEFAULT_SIZE, colors: int = DEFAULT_COLORS
) -> Path:
    """Make a sprite from ``path`` and save it next to it as PNG; return its path."""
    try:
        image, _ = imaging.load(path)
    except imaging.ImageError as exc:
        raise SpriteError(str(exc)) from exc
    sprite = make_sprite(image, size, colors)

    output = path.with_name(f"{path.stem}{OUTPUT_SUFFIX}{OUTPUT_EXTENSION}")
    try:
        sprite.save(output, format="PNG", optimize=True)
    except OSError as exc:
        raise SpriteError(f"cannot write {output}: {exc.strerror or exc}") from exc
    return output
