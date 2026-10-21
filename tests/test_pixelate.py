import random
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from toolbox import pixelate
from toolbox.cli import app

runner = CliRunner()


def noise(size=(100, 70), seed=1) -> Image.Image:
    """An RGBA image where every pixel differs, so any untouched area is detectable."""
    rng = random.Random(seed)
    image = Image.new("RGBA", size)
    image.putdata(
        [
            (rng.randrange(256), rng.randrange(256), rng.randrange(256), 255)
            for _ in range(size[0] * size[1])
        ]
    )
    return image


def block_colors(image: Image.Image, box: tuple[int, int, int, int]) -> set:
    colors = image.crop(box).getcolors(maxcolors=image.width * image.height)
    assert colors is not None
    return {color for _, color in colors}


def test_every_block_is_one_color_including_partial_edges():
    result = pixelate.pixelate(noise((100, 70)), block_size=16)
    assert result.size == (100, 70)
    for top in range(0, 70, 16):
        for left in range(0, 100, 16):
            box = (left, top, min(left + 16, 100), min(top + 16, 70))
            assert len(block_colors(result, box)) == 1, box


def test_block_is_the_average_color():
    image = Image.new("RGBA", (2, 2))
    image.putdata([(0, 0, 0, 255), (100, 0, 0, 255), (0, 200, 0, 255), (0, 0, 40, 255)])
    result = pixelate.pixelate(image, block_size=2)
    assert block_colors(result, (0, 0, 2, 2)) == {(25, 50, 10, 255)}


def test_transparent_pixels_do_not_darken_the_average():
    image = Image.new("RGBA", (2, 1))
    image.putdata([(255, 255, 255, 255), (0, 0, 0, 0)])  # white next to transparent
    pixel = pixelate.pixelate(image, block_size=2).getpixel((0, 0))
    assert isinstance(pixel, tuple)
    red, green, blue, alpha = pixel
    assert (red, green, blue) == (255, 255, 255)
    assert alpha == pytest.approx(128, abs=1)


@pytest.mark.parametrize(
    ("size", "expected"), [((640, 480), 10), ((6400, 100), 100), ((50, 50), 2)]
)
def test_auto_block_size_scales_with_the_longer_side(size, expected):
    assert pixelate.auto_block_size(size) == expected


def test_region_changes_only_the_region():
    image = noise((100, 70))
    region = pixelate.Region(20, 10, 40, 30)
    result = pixelate.pixelate(image, block_size=10, region=region)

    inside = (20, 10, 60, 40)
    assert len(block_colors(result, inside)) <= 12  # 4x3 blocks
    mask = Image.new("L", image.size, 255)
    mask.paste(0, inside)
    outside_before = Image.composite(image, Image.new("RGBA", image.size), mask)
    outside_after = Image.composite(result, Image.new("RGBA", image.size), mask)
    assert outside_before.tobytes() == outside_after.tobytes()


def test_region_past_the_edge_is_clipped():
    result = pixelate.pixelate(
        noise((100, 70)), block_size=10, region=pixelate.Region(90, 60, 500, 500)
    )
    assert result.size == (100, 70)
    assert len(block_colors(result, (90, 60, 100, 70))) == 1


def test_region_outside_the_image_is_rejected():
    with pytest.raises(pixelate.PixelateError, match="outside"):
        pixelate.pixelate(noise(), region=pixelate.Region(100, 0, 5, 5))


def test_block_size_below_minimum_is_rejected():
    with pytest.raises(pixelate.PixelateError):
        pixelate.pixelate(noise(), block_size=1)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10,20,30,40", pixelate.Region(10, 20, 30, 40)),
        (" 0, 0 ,1,1", pixelate.Region(0, 0, 1, 1)),
    ],
)
def test_parse_region(text, expected):
    assert pixelate.parse_region(text) == expected


@pytest.mark.parametrize(
    "text", ["", "1,2,3", "1,2,3,4,5", "a,b,c,d", "-1,0,5,5", "0,0,0,5"]
)
def test_parse_region_rejects_invalid(text):
    with pytest.raises(pixelate.PixelateError):
        pixelate.parse_region(text)


def test_pixelate_file_keeps_format_and_writes_next_to_source(tmp_path: Path):
    source = tmp_path / "photo.jpeg"
    noise().convert("RGB").save(source, format="JPEG")
    output = pixelate.pixelate_file(source, block_size=10)
    assert output == tmp_path / "photo_pixelated.jpeg"
    with Image.open(output) as result:
        assert result.format == "JPEG"
        assert result.size == (100, 70)


def test_cli_with_block_and_region(tmp_path: Path):
    source = tmp_path / "a.png"
    noise().save(source)
    result = runner.invoke(app, ["pixelate", str(source), "-b", "8", "-r", "0,0,50,50"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "a_pixelated.png").exists()


def test_cli_rejects_bad_region(tmp_path: Path):
    source = tmp_path / "a.png"
    noise().save(source)
    result = runner.invoke(app, ["pixelate", str(source), "-r", "1,2,3"])
    assert result.exit_code == 2
    assert not (tmp_path / "a_pixelated.png").exists()


def test_cli_continues_after_a_bad_file(tmp_path: Path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    good = tmp_path / "a.png"
    noise().save(good)
    result = runner.invoke(app, ["pixelate", str(bad), str(good)])
    assert result.exit_code == 1
    assert "cannot read image" in result.output
    assert (tmp_path / "a_pixelated.png").exists()
