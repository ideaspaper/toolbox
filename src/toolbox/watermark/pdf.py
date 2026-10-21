"""Watermark every page of a PDF without rasterizing it.

The stamp is embedded once as an image XObject and drawn in an extra content stream on
top of each page, so the original text stays selectable. Page /Rotate and CropBox
offsets are handled so the stamp looks upright where the reader sees it.
"""

import io
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NullObject,
    NumberObject,
    PdfObject,
    StreamObject,
)

from toolbox.watermark.stamp import Placement, Stamp, WatermarkError, place

STAMP_RESOURCE_NAME = "/WmStamp"
DEFAULT_PAGE_BOX = (0.0, 0.0, 612.0, 792.0)  # US Letter, only if a page has no MediaBox
MAX_PARENT_DEPTH = 64  # guard against broken or cyclic page trees

Box = tuple[float, float, float, float]


def watermark_pdf(path: Path, stamp: Stamp) -> bytes:
    """Return the bytes of ``path`` with ``stamp`` drawn on every page."""
    writer = PdfWriter(clone_from=_load(path))
    stamp_ref = _embed(writer, stamp.image)
    for page in writer.pages:
        _stamp_page(writer, page, stamp, stamp_ref)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _load(path: Path) -> PdfReader:
    try:
        reader = PdfReader(path)
        unlocked = not reader.is_encrypted or bool(reader.decrypt(""))
        page_count = len(reader.pages) if unlocked else 0
    except (OSError, PyPdfError, ValueError, KeyError) as exc:
        raise WatermarkError(f"cannot read PDF: {exc}") from exc
    if not unlocked:
        raise WatermarkError("the PDF is password-protected; unlock it first")
    if page_count == 0:
        raise WatermarkError("the PDF has no pages")
    return reader


def _add(writer: PdfWriter, obj: PdfObject) -> IndirectObject:
    # pypdf has no public way to register a standalone object in the output file.
    return writer._add_object(obj)


def _stream(data: bytes, entries: dict[str, PdfObject] | None = None) -> StreamObject:
    stream = DecodedStreamObject()
    stream.set_data(data)
    stream = stream.flate_encode()
    for key, value in (entries or {}).items():
        stream[NameObject(key)] = value
    return stream


def _image_xobject(image: Image.Image, color_space: str) -> StreamObject:
    return _stream(
        image.tobytes(),
        {
            "/Type": NameObject("/XObject"),
            "/Subtype": NameObject("/Image"),
            "/Width": NumberObject(image.width),
            "/Height": NumberObject(image.height),
            "/ColorSpace": NameObject(color_space),
            "/BitsPerComponent": NumberObject(8),
        },
    )


def _embed(writer: PdfWriter, image: Image.Image) -> IndirectObject:
    """Embed the RGBA stamp once (RGB + alpha soft mask) for every page to share."""
    xobject = _image_xobject(image.convert("RGB"), "/DeviceRGB")
    xobject[NameObject("/SMask")] = _add(
        writer, _image_xobject(image.getchannel("A"), "/DeviceGray")
    )
    return _add(writer, xobject)


def _stamp_page(
    writer: PdfWriter, page: DictionaryObject, stamp: Stamp, stamp_ref: IndirectObject
) -> None:
    box, rotation = _visible_box(page), _rotation(page)
    width, height = box[2] - box[0], box[3] - box[1]
    if rotation in (90, 270):
        width, height = height, width
    if width <= 0 or height <= 0:
        return

    name = _register(page, stamp_ref)
    matrix = _viewer_to_pdf(box, rotation)
    overlay = _overlay(matrix, width, height, place(stamp, width, height), name)
    # Wrap the original content in q/Q so its graphics state can't leak out.
    opening = _add(writer, _stream(b"q\n"))
    closing = _add(writer, _stream(f"\nQ\n{overlay}\n".encode("ascii")))
    page[NameObject("/Contents")] = ArrayObject(
        [opening, *_content_refs(writer, page), closing]
    )


def _inherited(page: DictionaryObject, key: str) -> PdfObject | None:
    """Read a page attribute, following /Parent for inherited values."""
    node = page
    for _ in range(MAX_PARENT_DEPTH):
        if not isinstance(node, DictionaryObject):
            return None
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        if parent is None:
            return None
        node = parent.get_object()
    return None


def _read_box(value: PdfObject | None) -> Box | None:
    if not isinstance(value, ArrayObject) or len(value) != 4:
        return None
    numbers = [item.get_object() for item in value]
    if not all(isinstance(number, (int, float)) for number in numbers):
        return None
    x_a, y_a, x_b, y_b = (float(number) for number in numbers)
    return min(x_a, x_b), min(y_a, y_b), max(x_a, x_b), max(y_a, y_b)


def _visible_box(page: DictionaryObject) -> Box:
    """The CropBox clipped to the MediaBox, in PDF user space."""
    media = _read_box(_inherited(page, "/MediaBox")) or DEFAULT_PAGE_BOX
    crop = _read_box(_inherited(page, "/CropBox"))
    if crop is None:
        return media
    box = (
        max(crop[0], media[0]),
        max(crop[1], media[1]),
        min(crop[2], media[2]),
        min(crop[3], media[3]),
    )
    return box if box[0] < box[2] and box[1] < box[3] else media


def _rotation(page: DictionaryObject) -> int:
    """Page /Rotate normalized to 0, 90, 180 or 270 (clockwise)."""
    angle = _inherited(page, "/Rotate")
    if not isinstance(angle, (int, float)):  # NumberObject / FloatObject subclass these
        return 0
    return round(angle / 90) * 90 % 360


def _viewer_to_pdf(box: Box, rotation: int) -> tuple[float, ...]:
    """Matrix from upright viewer space (origin bottom-left) to PDF user space."""
    x0, y0, x1, y1 = box
    return {
        0: (1, 0, 0, 1, x0, y0),
        90: (0, 1, -1, 0, x1, y0),
        180: (-1, 0, 0, -1, x1, y1),
        270: (0, -1, 1, 0, x0, y1),
    }[rotation]


def _numbers(*values: float) -> str:
    """Compact PDF numbers: at most 4 decimals, no trailing zeros."""

    def format_one(value: float) -> str:
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text

    return " ".join(format_one(value) for value in values)


def _overlay(
    matrix: tuple[float, ...],
    width: float,
    height: float,
    placement: Placement,
    name: str,
) -> str:
    """Operators painting the stamp at each position, clipped to the visible page."""
    size = _numbers(placement.width, 0, 0, placement.height)
    ops = ["q", f"{_numbers(*matrix)} cm", f"0 0 {_numbers(width, height)} re W n"]
    for x, y in placement.positions:
        # Placement is top-left with y down; PDF draws from the bottom-left with y up.
        bottom = height - y - placement.height
        ops.append(f"q {size} {_numbers(x, bottom)} cm {name} Do Q")
    ops.append("Q")
    return "\n".join(ops)


def _register(page: DictionaryObject, stamp_ref: IndirectObject) -> str:
    """Add the stamp to the page's /XObject resources and return its resource name."""
    resources = _inherited(
        page, "/Resources"
    )  # may be shared with a parent: update in place
    if not isinstance(resources, DictionaryObject):
        resources = DictionaryObject()
        page[NameObject("/Resources")] = resources
    xobjects = resources.get("/XObject")
    xobjects = xobjects.get_object() if xobjects is not None else None
    if not isinstance(xobjects, DictionaryObject):
        xobjects = DictionaryObject()
        resources[NameObject("/XObject")] = xobjects

    name, suffix = STAMP_RESOURCE_NAME, 0
    while name in xobjects and xobjects.raw_get(name) != stamp_ref:
        suffix += 1
        name = f"{STAMP_RESOURCE_NAME}{suffix}"
    xobjects[NameObject(name)] = stamp_ref
    return name


def _content_refs(writer: PdfWriter, page: DictionaryObject) -> list[IndirectObject]:
    """The page's existing content streams as references, kept as-is."""
    if "/Contents" not in page:
        return []
    raw = page.raw_get("/Contents")
    resolved = raw.get_object()
    if isinstance(resolved, NullObject):
        return []
    items = list(resolved) if isinstance(resolved, ArrayObject) else [raw]
    return [
        item if isinstance(item, IndirectObject) else _add(writer, item)
        for item in items
    ]
