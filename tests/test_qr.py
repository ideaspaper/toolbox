import struct

import pytest

from toolbox import qr


def png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_generate_png_has_expected_dimensions():
    image = qr.generate("hello", qr.QROptions(scale=3, border=4))
    # "hello" fits in a version 1 symbol (21 modules) at level M.
    assert png_size(image) == ((21 + 2 * 4) * 3,) * 2


def test_generate_svg_uses_requested_colors():
    options = qr.QROptions(
        foreground="navy", background="#ffe", image_format=qr.ImageFormat.SVG
    )
    image = qr.generate("hello", options).decode()
    assert image.lstrip().startswith("<?xml")
    assert "#000080" in image.lower() or "navy" in image.lower()


def test_generate_handles_unicode():
    assert qr.generate("こんにちは 👋").startswith(b"\x89PNG")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("black", "#000000"),
        (" Navy ", "#000080"),
        ("#abc", "#AABBCC"),
        ("12ab3F", "#12AB3F"),
    ],
)
def test_parse_color(value, expected):
    assert qr.parse_color(value) == expected


@pytest.mark.parametrize("value", ["", "notacolor", "#12345", "#GGGGGG"])
def test_parse_color_rejects_invalid(value):
    with pytest.raises(qr.QRError):
        qr.parse_color(value)


def test_contrast_ratio_bounds():
    assert qr.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert qr.contrast_ratio("#777777", "#777777") == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("data", "options", "message"),
    [
        ("   ", qr.QROptions(), "empty"),
        ("hi", qr.QROptions(foreground="#777777", background="#888888"), "too similar"),
        ("x" * 3000, qr.QROptions(error_correction=qr.ErrorCorrection.H), "too long"),
        ("x" * 2000, qr.QROptions(scale=50, border=20), "max"),
    ],
)
def test_generate_rejects_bad_input(data, options, message):
    with pytest.raises(qr.QRError, match=message):
        qr.generate(data, options)


def test_render_terminal_returns_block_characters():
    assert "█" in qr.render_terminal("hello")
