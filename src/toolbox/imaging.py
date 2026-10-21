"""Shared raster image I/O: load upright as RGBA, save back in the source's format.

Saving keeps the original format, EXIF, color profile, DPI and transparency where the
format supports them, and falls back to PNG when it cannot be written.
"""

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

FALLBACK_FORMAT = "PNG"
FORMAT_ALIASES = {"MPO": "JPEG"}  # multi-picture JPEGs from phones and cameras
EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "GIF": ".gif",
    "TIFF": ".tif",
}
SAVE_OPTIONS = {
    "JPEG": {"quality": 95},
    "WEBP": {"quality": 95},
    "TIFF": {"compression": "tiff_lzw"},
}
METADATA_KEYS = ("exif", "icc_profile", "dpi")
METADATA_FORMATS = {"JPEG", "PNG", "WEBP"}  # formats that reliably store this metadata
ALPHA_MODES = {"RGBA", "RGBa", "LA", "La", "PA"}
GIF_TRANSPARENT_INDEX = 255  # palette slot reserved for transparent pixels


class ImageError(ValueError):
    """Raised when an image cannot be read."""


@dataclass
class Source:
    """What is needed to save an edited image like the file it came from."""

    format: str
    suffix: str
    has_alpha: bool
    metadata: dict = field(default_factory=dict)


def load(path: Path) -> tuple[Image.Image, Source]:
    """Open the image upright (EXIF orientation applied) as RGBA, plus its details."""
    try:
        with Image.open(path) as original:
            upright = _upright(original)
            source_format = original.format or ""
            source = Source(
                format=FORMAT_ALIASES.get(source_format, source_format),
                suffix=path.suffix,
                has_alpha=upright.mode in ALPHA_MODES or "transparency" in upright.info,
                metadata={
                    key: upright.info[key]
                    for key in METADATA_KEYS
                    if upright.info.get(key)
                },
            )
            image = upright.convert("RGBA")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImageError(f"cannot read image: {exc}") from exc
    if upright.mode == "CMYK":
        # A CMYK profile would corrupt the colors of the RGB output.
        source.metadata.pop("icc_profile", None)
    return image, source


def encode(image: Image.Image, source: Source) -> tuple[bytes, str]:
    """Encode ``image`` like ``source``; return the bytes and the file extension."""
    output_format = source.format if source.format in EXTENSIONS else FALLBACK_FORMAT
    try:
        data = _encode(image, output_format, source.has_alpha, source.metadata)
    except (OSError, ValueError, KeyError, TypeError):
        output_format = FALLBACK_FORMAT  # this format/mode cannot be written: plain PNG
        data = _encode(image, output_format, source.has_alpha, {})

    if output_format == source.format:
        return data, source.suffix
    return data, EXTENSIONS[output_format]


def _upright(image: Image.Image) -> Image.Image:
    """Apply the EXIF orientation; a corrupt EXIF block leaves the image as it is."""
    try:
        return ImageOps.exif_transpose(image)
    except Exception:  # Pillow raises assorted errors on malformed EXIF data
        return image.copy()


def _encode(
    image: Image.Image, output_format: str, has_alpha: bool, metadata: dict
) -> bytes:
    if output_format == "JPEG" or not has_alpha:
        image = image.convert("RGB")
    if output_format == "GIF":
        image = _to_gif_palette(image)
    options = dict(SAVE_OPTIONS.get(output_format, {}))
    if output_format in METADATA_FORMATS:
        options.update(metadata)
    buffer = io.BytesIO()
    image.save(buffer, format=output_format, **options)
    return buffer.getvalue()


def _to_gif_palette(image: Image.Image) -> Image.Image:
    """Quantize for GIF, reserving one palette slot for fully transparent pixels."""
    if image.mode != "RGBA":
        return image.quantize(colors=256)
    palette_image = image.convert("RGB").quantize(colors=255)  # index 255 stays free
    # Lookup table: alpha below 128 becomes a transparent pixel.
    transparent = image.getchannel("A").point([255] * 128 + [0] * 128)
    palette_image.paste(GIF_TRANSPARENT_INDEX, mask=transparent)
    palette_image.info["transparency"] = GIF_TRANSPARENT_INDEX
    return palette_image
