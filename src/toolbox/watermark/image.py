"""Watermark raster images, keeping the original format and metadata where possible."""

from pathlib import Path

from PIL import Image

from toolbox import imaging
from toolbox.watermark.stamp import Stamp, WatermarkError, place


def watermark_image(path: Path, stamp: Stamp) -> tuple[bytes, str]:
    """Return the watermarked image bytes and the file extension to save them with."""
    try:
        image, source = imaging.load(path)
    except imaging.ImageError as exc:
        raise WatermarkError(str(exc)) from exc
    _paste(image, stamp)
    return imaging.encode(image, source)


def _paste(image: Image.Image, stamp: Stamp) -> None:
    placement = place(stamp, image.width, image.height)
    size = (max(1, round(placement.width)), max(1, round(placement.height)))
    resized = stamp.image.resize(size, Image.Resampling.LANCZOS)
    for x, y in placement.positions:
        left, top = round(x), round(y)
        # alpha_composite rejects negative destinations, so clip the stamp to the image.
        box = (
            max(0, -left),
            max(0, -top),
            min(size[0], image.width - left),
            min(size[1], image.height - top),
        )
        if box[2] > box[0] and box[3] > box[1]:
            image.alpha_composite(
                resized, dest=(left + box[0], top + box[1]), source=box
            )
