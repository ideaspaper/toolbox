from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from typer.testing import CliRunner

from toolbox import watermark
from toolbox.cli import app
from toolbox.watermark.stamp import place

runner = CliRunner()


def make_image(path: Path, mode: str = "RGB", size=(300, 200), **save_options) -> Path:
    Image.new(mode, size, "white").save(path, **save_options)
    return path


def make_pdf(path: Path, rotate: int = 0, password: str | None = None) -> Path:
    """A one-page PDF with real (extractable) text."""
    writer = PdfWriter()
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 24 Tf 72 720 Td (Original text) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    if rotate:
        page.rotate(rotate)
    if password:
        writer.encrypt(password)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


@pytest.fixture
def text_stamp():
    return watermark.text_stamp("CONFIDENTIAL", 0.4)


def test_detect_kind(tmp_path):
    assert watermark.detect_kind(make_pdf(tmp_path / "a.pdf")) is watermark.FileKind.PDF
    # Detection uses the content, so a misnamed file is still recognised.
    image = make_image(tmp_path / "photo.pdf.bin", format="PNG")
    assert watermark.detect_kind(image) is watermark.FileKind.IMAGE
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello")
    with pytest.raises(watermark.WatermarkError, match="unsupported"):
        watermark.detect_kind(text_file)


def test_text_stamp_rejects_blank_text():
    with pytest.raises(watermark.WatermarkError):
        watermark.text_stamp("  ", 0.4)


def test_text_stamp_applies_opacity(text_stamp):
    assert text_stamp.image.getchannel("A").getextrema() == (0, round(255 * 0.4))


def test_tiled_placement_is_dense_and_inside_the_area(text_stamp):
    placement = place(text_stamp, 1000, 800)
    assert len(placement.positions) > 50
    for x, y in placement.positions:
        assert x < 1000 and y < 800
        assert x + placement.width > 0 and y + placement.height > 0


def test_image_stamp_is_centered(tmp_path):
    stamp = watermark.image_stamp(
        make_image(tmp_path / "logo.png", "RGBA", (100, 50)), 0.4
    )
    placement = place(stamp, 1000, 1000)
    assert placement.width == pytest.approx(800)
    assert placement.positions == [(pytest.approx(100), pytest.approx(300))]


@pytest.mark.parametrize(
    ("name", "save_format", "mode"),
    [
        ("a.jpeg", "JPEG", "RGB"),
        ("a.png", "PNG", "RGBA"),
        ("a.webp", "WEBP", "RGB"),
        ("a.gif", "GIF", "P"),
        ("a.tiff", "TIFF", "RGB"),
        ("a.bmp", "BMP", "RGB"),
    ],
)
def test_image_keeps_format_and_extension(
    tmp_path, text_stamp, name, save_format, mode
):
    source = make_image(tmp_path / name, mode, format=save_format)
    output = watermark.watermark_file(source, text_stamp)
    assert output == tmp_path / f"a_watermarked{source.suffix}"
    with Image.open(output) as result:
        assert result.format == save_format
        assert result.size == (300, 200)
        white_pixels = result.convert("L").histogram()[255]
        assert white_pixels < 300 * 200  # something was drawn


def test_image_keeps_transparency(tmp_path, text_stamp):
    source = make_image(tmp_path / "a.png", "RGBA", format="PNG")
    with Image.open(watermark.watermark_file(source, text_stamp)) as result:
        assert result.mode == "RGBA"


def test_unwritable_format_falls_back_to_png(tmp_path, text_stamp):
    source = make_image(tmp_path / "icon.ico", format="ICO", size=(64, 64))
    output = watermark.watermark_file(source, text_stamp)
    assert output.name == "icon_watermarked.png"


def test_image_respects_exif_orientation(tmp_path, text_stamp):
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise when displayed
    source = make_image(tmp_path / "a.jpg", size=(300, 200), format="JPEG", exif=exif)
    with Image.open(watermark.watermark_file(source, text_stamp)) as result:
        assert result.size == (200, 300)
        assert result.getexif().get(0x0112) in (None, 1)


@pytest.mark.parametrize("rotate", [0, 90])
def test_pdf_keeps_text_and_shares_one_stamp(tmp_path, text_stamp, rotate):
    output = watermark.watermark_file(
        make_pdf(tmp_path / "doc.pdf", rotate), text_stamp
    )
    assert output.name == "doc_watermarked.pdf"
    reader = PdfReader(output)
    page = reader.pages[0]
    assert "Original text" in page.extract_text()
    assert page.rotation == rotate
    resources = page["/Resources"]
    assert isinstance(resources, DictionaryObject)
    xobjects = resources["/XObject"]
    assert isinstance(xobjects, DictionaryObject)
    assert list(xobjects) == ["/WmStamp"]  # one stamp shared by all tiles
    contents = page.get_contents()
    assert contents is not None
    assert b"/WmStamp Do" in contents.get_data()


def test_pdf_with_password_is_rejected(tmp_path, text_stamp):
    with pytest.raises(watermark.WatermarkError, match="password"):
        watermark.watermark_file(
            make_pdf(tmp_path / "doc.pdf", password="secret"), text_stamp
        )


def test_broken_pdf_is_rejected(tmp_path, text_stamp):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nnot really a pdf")
    with pytest.raises(watermark.WatermarkError):
        watermark.watermark_file(broken, text_stamp)


def test_cli_watermarks_several_files(tmp_path):
    image = make_image(tmp_path / "a.png", format="PNG")
    pdf = make_pdf(tmp_path / "b.pdf")
    result = runner.invoke(app, ["watermark", str(image), str(pdf), "-t", "DRAFT"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "a_watermarked.png").exists()
    assert (tmp_path / "b_watermarked.pdf").exists()


def test_cli_with_image_and_opacity(tmp_path):
    source = make_image(tmp_path / "a.jpg", format="JPEG")
    logo = make_image(tmp_path / "logo.png", "RGBA", (50, 50), format="PNG")
    result = runner.invoke(app, ["watermark", str(source), "-i", str(logo), "-p", "80"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("extra", [[], ["-t", "x", "-i", "logo.png"]])
def test_cli_requires_exactly_one_watermark(tmp_path, extra):
    source = make_image(tmp_path / "a.png", format="PNG")
    make_image(tmp_path / "logo.png", format="PNG")
    extra = [str(tmp_path / arg) if arg == "logo.png" else arg for arg in extra]
    result = runner.invoke(app, ["watermark", str(source), *extra])
    assert result.exit_code == 2


def test_cli_rejects_out_of_range_opacity(tmp_path):
    source = make_image(tmp_path / "a.png", format="PNG")
    result = runner.invoke(app, ["watermark", str(source), "-t", "x", "-p", "0"])
    assert result.exit_code == 2


def test_cli_continues_after_a_bad_file(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    good = make_image(tmp_path / "a.png", format="PNG")
    result = runner.invoke(app, ["watermark", str(bad), str(good), "-t", "x"])
    assert result.exit_code == 1
    assert "unsupported" in result.output
    assert (tmp_path / "a_watermarked.png").exists()
