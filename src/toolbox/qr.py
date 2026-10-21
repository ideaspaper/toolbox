"""QR code generation: input validation and rendering to PNG or SVG bytes.

This module has no CLI concerns so it can be reused and tested on its own.
"""

import io
from dataclasses import dataclass
from enum import StrEnum

import segno

MAX_IMAGE_SIZE = 10_000
MIN_CONTRAST_RATIO = 3.0

_NAMED_COLORS = {
    "black": "#000000",
    "white": "#FFFFFF",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#C0C0C0",
    "red": "#FF0000",
    "maroon": "#800000",
    "orange": "#FFA500",
    "yellow": "#FFFF00",
    "olive": "#808000",
    "lime": "#00FF00",
    "green": "#008000",
    "teal": "#008080",
    "cyan": "#00FFFF",
    "aqua": "#00FFFF",
    "blue": "#0000FF",
    "navy": "#000080",
    "purple": "#800080",
    "magenta": "#FF00FF",
    "fuchsia": "#FF00FF",
    "pink": "#FFC0CB",
    "brown": "#A52A2A",
}


class QRError(ValueError):
    """Raised when QR options are invalid or the data cannot be encoded."""


class ErrorCorrection(StrEnum):
    L = "L"
    M = "M"
    Q = "Q"
    H = "H"


class ImageFormat(StrEnum):
    PNG = "png"
    SVG = "svg"


@dataclass(frozen=True)
class QROptions:
    error_correction: ErrorCorrection = ErrorCorrection.M
    foreground: str = "black"
    background: str = "white"
    scale: int = 10
    border: int = 4
    image_format: ImageFormat = ImageFormat.PNG


def parse_color(value: str) -> str:
    """Return ``value`` as ``#RRGGBB``.

    Accepts a common color name, ``#RGB`` or ``#RRGGBB``.
    """
    text = value.strip().lower()
    if text in _NAMED_COLORS:
        return _NAMED_COLORS[text]
    hex_digits = text.removeprefix("#")
    if len(hex_digits) == 3:
        hex_digits = "".join(digit * 2 for digit in hex_digits)
    if len(hex_digits) == 6 and all(
        digit in "0123456789abcdef" for digit in hex_digits
    ):
        return "#" + hex_digits.upper()
    raise QRError(f"invalid color {value!r}: use a common color name or #RRGGBB")


def contrast_ratio(color_a: str, color_b: str) -> float:
    """WCAG contrast ratio between two ``#RRGGBB`` colors, from 1.0 to 21.0."""
    lighter, darker = sorted(
        (_relative_luminance(color_a), _relative_luminance(color_b)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(hex_color: str) -> float:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def _encode(data: str, error_correction: ErrorCorrection) -> segno.QRCode:
    if not data.strip():
        raise QRError("data must not be empty")
    try:
        # boost_error=False keeps the error correction level the caller asked for.
        return segno.make(
            data, error=error_correction.value, micro=False, boost_error=False
        )
    except segno.DataOverflowError as exc:
        raise QRError(
            "data is too long for a QR code at error correction level "
            f"{error_correction}"
        ) from exc


def generate(data: str, options: QROptions | None = None) -> bytes:
    """Encode ``data`` as a QR code and return the rendered image bytes."""
    options = options or QROptions()
    if options.scale < 1:
        raise QRError("scale must be at least 1")
    if options.border < 0:
        raise QRError("border must not be negative")

    foreground = parse_color(options.foreground)
    background = parse_color(options.background)
    if contrast_ratio(foreground, background) < MIN_CONTRAST_RATIO:
        raise QRError(
            "foreground and background colors are too similar to scan reliably"
        )

    code = _encode(data, options.error_correction)

    width, _ = code.symbol_size(scale=options.scale, border=options.border)
    if width > MAX_IMAGE_SIZE:
        raise QRError(
            f"image would be {width}px wide (max {MAX_IMAGE_SIZE}px); "
            "lower scale or border"
        )

    buffer = io.BytesIO()
    code.save(
        buffer,
        kind=options.image_format.value,
        scale=options.scale,
        border=options.border,
        dark=foreground,
        light=background,
    )
    return buffer.getvalue()


def render_terminal(data: str, options: QROptions | None = None) -> str:
    """Render ``data`` as a QR code made of block characters for terminal display."""
    options = options or QROptions()
    code = _encode(data, options.error_correction)
    buffer = io.StringIO()
    code.terminal(out=buffer, border=options.border, compact=True)
    return buffer.getvalue()
