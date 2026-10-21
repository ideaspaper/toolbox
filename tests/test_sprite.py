from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from toolbox import sprite
from toolbox.cli import app

runner = CliRunner()

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
CLEAR = (0, 0, 0, 0)


def pixels(image: Image.Image) -> list:
    return list(image.get_flattened_data())


def character(size=256) -> Image.Image:
    """An anti-aliased figure on a transparent background, like real sprite sources."""
    big = Image.new("RGBA", (size * 4, size * 4), CLEAR)
    draw = ImageDraw.Draw(big)
    draw.ellipse((size, size // 2, size * 3, size * 2), fill=(250, 210, 170, 255))
    draw.rectangle((size, size * 2, size * 3, size * 4 - 20), fill=(60, 110, 200, 255))
    return big.resize((size, size), Image.Resampling.LANCZOS)


@pytest.mark.parametrize(
    ("image_size", "size", "expected"),
    [((100, 50), 20, (20, 10)), ((50, 100), 20, (10, 20)), ((1000, 3), 10, (10, 1))],
)
def test_sprite_size_keeps_aspect_ratio(image_size, size, expected):
    assert sprite.sprite_size(image_size, size) == expected


def test_cell_takes_the_most_common_color_not_the_average():
    image = Image.new("RGBA", (4, 4), RED)
    ImageDraw.Draw(image).rectangle((0, 0, 3, 1), fill=BLUE)  # 8 blue, 8 red: tie
    image.putpixel((0, 3), BLUE)  # 9 blue, 7 red
    result = sprite.make_sprite(image, size=1, colors=2)
    assert pixels(result) == [BLUE]


def test_cell_is_opaque_from_a_third_of_opaque_pixels():
    mostly_clear = Image.new("RGBA", (6, 1), CLEAR)
    for x in range(2):  # 2 of 6 opaque: exactly a third
        mostly_clear.putpixel((x, 0), RED)
    assert pixels(sprite.make_sprite(mostly_clear, size=1, colors=2)) == [RED]

    mostly_clear.putpixel((1, 0), CLEAR)  # 1 of 6
    assert pixels(sprite.make_sprite(mostly_clear, size=1, colors=2)) == [CLEAR]


def test_transparent_pixels_do_not_affect_the_palette():
    image = Image.new("RGBA", (4, 4), (0, 255, 0, 0))  # invisible green
    ImageDraw.Draw(image).rectangle((0, 0, 3, 1), fill=RED)
    result = sprite.make_sprite(image, size=4, colors=2)
    assert {p for p in pixels(result) if p[3]} == {RED}


def test_output_has_hard_alpha_and_a_limited_palette():
    result = sprite.make_sprite(character(), size=32, colors=8)
    assert result.size == (32, 32)
    assert {p[3] for p in pixels(result)} == {0, 255}
    assert len({p for p in pixels(result) if p[3]}) <= 8


def test_small_accent_colors_survive():
    image = character()
    ImageDraw.Draw(image).rectangle((110, 90, 145, 100), fill=(160, 40, 40, 255))
    result = sprite.make_sprite(image, size=32, colors=8)
    reds = [p for p in pixels(result) if p[3] and p[0] > 120 and p[1] < 80]
    assert reds, "the small red accent was merged into another color"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"size": 300}, "larger"),
        ({"size": 0}, "between"),
        ({"colors": 1}, "between"),
        ({"colors": 256}, "between"),
    ],
)
def test_invalid_options_are_rejected(kwargs, message):
    with pytest.raises(sprite.SpriteError, match=message):
        sprite.make_sprite(character(), **kwargs)


def test_fully_transparent_image_is_rejected():
    with pytest.raises(sprite.SpriteError, match="transparent"):
        sprite.make_sprite(Image.new("RGBA", (10, 10), CLEAR), size=5)


def test_sprite_file_is_always_png(tmp_path: Path):
    source = tmp_path / "hero.jpg"
    character().convert("RGB").save(source, format="JPEG")
    output = sprite.sprite_file(source, size=16, colors=4)
    assert output == tmp_path / "hero_sprite.png"
    with Image.open(output) as result:
        assert result.format == "PNG"
        assert result.size == (16, 16)


def test_cli_makes_sprites(tmp_path: Path):
    source = tmp_path / "hero.png"
    character().save(source)
    result = runner.invoke(app, ["sprite", str(source), "-s", "24", "-c", "6"])
    assert result.exit_code == 0, result.output
    with Image.open(tmp_path / "hero_sprite.png") as output:
        assert output.size == (24, 24)


def test_cli_reports_a_size_larger_than_the_image(tmp_path: Path):
    source = tmp_path / "tiny.png"
    Image.new("RGBA", (8, 8), RED).save(source)
    result = runner.invoke(app, ["sprite", str(source), "-s", "16"])
    assert result.exit_code == 1
    assert "larger" in result.output
