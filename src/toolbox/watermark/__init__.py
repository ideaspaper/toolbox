"""Watermark images and PDFs with a tiled text stamp or a centered image stamp."""

from enum import StrEnum
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from toolbox.watermark.image import watermark_image
from toolbox.watermark.pdf import watermark_pdf
from toolbox.watermark.stamp import Stamp, WatermarkError, image_stamp, text_stamp

__all__ = [
    "FileKind",
    "Stamp",
    "WatermarkError",
    "detect_kind",
    "image_stamp",
    "text_stamp",
    "watermark_file",
]

OUTPUT_SUFFIX = "_watermarked"
PDF_HEADER_WINDOW = 1024  # readers accept junk before %PDF- within the first 1 KB


class FileKind(StrEnum):
    PDF = "pdf"
    IMAGE = "image"


def detect_kind(path: Path) -> FileKind:
    """Classify ``path`` by its content, not its extension."""
    try:
        with path.open("rb") as handle:
            if b"%PDF-" in handle.read(PDF_HEADER_WINDOW):
                return FileKind.PDF
        with Image.open(path):
            return FileKind.IMAGE
    except UnidentifiedImageError:
        raise WatermarkError(
            "unsupported file type; expected an image or a PDF"
        ) from None
    except OSError as exc:
        raise WatermarkError(f"cannot read file: {exc.strerror or exc}") from exc


def watermark_file(path: Path, stamp: Stamp) -> Path:
    """Watermark ``path`` and write the result next to it; return the output path."""
    if detect_kind(path) is FileKind.PDF:
        data, extension = watermark_pdf(path, stamp), ".pdf"
    else:
        data, extension = watermark_image(path, stamp)
    output = path.with_name(f"{path.stem}{OUTPUT_SUFFIX}{extension}")
    try:
        output.write_bytes(data)
    except OSError as exc:
        raise WatermarkError(f"cannot write {output}: {exc.strerror or exc}") from exc
    return output
