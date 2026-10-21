import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from toolbox.cli import app
from toolbox.pixel import draw, model, render, text
from toolbox.pixel.model import PixelError

runner = CliRunner()

SPRITE = '''
size = [4, 3]

[palette]
k = "#1d1d2b outline"
s = "#F2C9A080"

[animations.idle]
frames = [
"""
.kk.
kssk
.kk.
""",
]
'''


def grid(*rows: str) -> model.Grid:
    return [list(row) for row in rows]


def rows(g: model.Grid) -> list[str]:
    return ["".join(row) for row in g]


# --- format -------------------------------------------------------------------------


def test_loads_parses_palette_names_and_alpha():
    sprite = model.loads(SPRITE)
    assert (sprite.width, sprite.height) == (4, 3)
    assert sprite.palette["k"] == model.Color("#1D1D2B", "outline")
    assert sprite.palette["s"].rgba == (0xF2, 0xC9, 0xA0, 0x80)
    assert rows(sprite.frame()) == [".kk.", "kssk", ".kk."]


def test_dumps_round_trips():
    sprite = model.loads(SPRITE)
    assert model.loads(model.dumps(sprite)) == sprite


def test_loads_allows_indented_grids():
    indented = SPRITE.replace(
        "\n.kk.\nkssk\n.kk.\n", "\n    .kk.\n    kssk\n    .kk.\n"
    )
    assert rows(model.loads(indented).frame()) == [".kk.", "kssk", ".kk."]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("kssk", "ksk"), "row 1: has 3 pixels, expected 4"),
        (("kssk", "kszk"), "row 1, column 2: 'z' is not in the palette"),
        (('\n.kk.\n"""', '\n"""'), "has 2 rows, expected 3"),
        (('k = "#1d1d2b outline"', 'k = "red"'), "palette.k: invalid color"),
        (('k = "#1d1d2b outline"', 'kk = "#000000"'), "single letter or digit"),
        (("size = [4, 3]", "size = [4]"), "size must be"),
        (("size = [4, 3]", "size = [4, 3]\nsizes = 1"), "unknown key"),
        (("[animations.idle]", "[animations.bad name]"), "not valid TOML"),
    ],
)
def test_loads_reports_exact_problems(change, message):
    with pytest.raises(PixelError, match=message.replace("(", r"\(")):
        model.loads(SPRITE.replace(*change))


def test_frame_lookup_errors_list_what_exists():
    sprite = model.loads(SPRITE)
    with pytest.raises(PixelError, match="the sprite has: idle"):
        sprite.frame("walk")
    with pytest.raises(PixelError, match="frames 0-0"):
        sprite.frame("idle", 3)
    with pytest.raises(PixelError, match="use one of: . k s"):
        sprite.check_key("z")


@pytest.mark.parametrize(("text_", "expected"), [("16x8", (16, 8)), ("4X4", (4, 4))])
def test_parse_size(text_, expected):
    assert model.parse_size(text_) == expected


@pytest.mark.parametrize("bad", ["16", "0x4", "300x4", "axb"])
def test_parse_size_rejects(bad):
    with pytest.raises(PixelError):
        model.parse_size(bad)


# --- drawing ------------------------------------------------------------------------

BLANK = grid("....", "....", "....")


def test_line_includes_both_ends_and_handles_diagonals():
    assert rows(draw.line(BLANK, (0, 0), (3, 2), "k")) == ["k...", ".kk.", "...k"]
    assert rows(draw.line(BLANK, (3, 0), (0, 0), "k")) == ["kkkk", "....", "...."]


def test_rect_outline_and_filled():
    assert rows(draw.rect(BLANK, (3, 2), (0, 0), "k")) == ["kkkk", "k..k", "kkkk"]
    assert rows(draw.rect(BLANK, (1, 0), (2, 2), "k", filled=True)) == [
        ".kk.",
        ".kk.",
        ".kk.",
    ]


def test_ellipse_outline_and_filled():
    blank = grid(*["........"] * 8)
    assert rows(draw.ellipse(blank, (7, 7), (0, 0), "k")) == [
        "..kkkk..",
        ".k....k.",
        "k......k",
        "k......k",
        "k......k",
        "k......k",
        ".k....k.",
        "..kkkk..",
    ]
    assert rows(draw.ellipse(blank, (1, 1), (5, 3), "k", filled=True)) == [
        "........",
        "..kkk...",
        ".kkkkk..",
        "..kkk...",
        *["........"] * 4,
    ]


def test_ellipse_always_reaches_the_box_edges():
    thin = draw.ellipse(grid(*["...."] * 6), (1, 0), (2, 5), "k")
    assert rows(thin) == [".kk."] * 6


def test_polygon_outline_and_filled():
    blank = grid(*["......"] * 5)
    triangle = [(0, 4), (5, 4), (0, 0)]
    assert rows(draw.polygon(blank, triangle, "k")) == [
        "k.....",
        "kk....",
        "k.kk..",
        "k...k.",
        "kkkkkk",
    ]
    assert rows(draw.polygon(blank, triangle, "k", filled=True)) == [
        "k.....",
        "kk....",
        "kkkk..",
        "kkkkk.",
        "kkkkkk",
    ]


def test_polygon_needs_three_corners_inside_the_frame():
    with pytest.raises(PixelError, match="at least 3 corners, got 2"):
        draw.polygon(BLANK, [(0, 0), (3, 2)], "k")
    with pytest.raises(PixelError, match="outside the 4x3 frame"):
        draw.polygon(BLANK, [(0, 0), (3, 2), (4, 0)], "k")


def test_points_outside_the_frame_are_rejected_without_changes():
    with pytest.raises(PixelError, match="outside the 4x3 frame"):
        draw.set_pixels(BLANK, [(1, 1), (4, 0)], "k")


def test_fill_stops_at_other_colors():
    shape = grid("k...", "k.k.", "kk..")
    assert rows(draw.fill(shape, (1, 0), "s")) == ["ksss", "ksks", "kkss"]


def test_mirror_and_flip():
    left = grid("ab..", "c...", "....")
    assert rows(draw.mirror(left, draw.Side.LEFT)) == ["abba", "c..c", "...."]
    assert rows(draw.flip(left, draw.Direction.HORIZONTAL)) == ["..ba", "...c", "...."]
    assert rows(draw.flip(left, draw.Direction.VERTICAL)) == ["....", "c...", "ab.."]


def test_shift_drops_or_wraps():
    shape = grid("k...", "....", "...s")
    assert rows(draw.shift(shape, 1, 0)) == [".k..", "....", "...."]
    assert rows(draw.shift(shape, 1, 0, wrap=True)) == [".k..", "....", "s..."]


def test_outline_only_touches_transparent_neighbors():
    dot = grid("....", ".s..", "....")
    assert rows(draw.outline(dot, "k")) == [".k..", "ksk.", ".k.."]
    assert rows(draw.outline(dot, "k", diagonal=True)) == ["kkk.", "ksk.", "kkk."]


# --- rendering and import -----------------------------------------------------------


def two_animation_sprite() -> model.Sprite:
    sprite = model.loads(SPRITE)
    frame = sprite.frame_at()
    sprite.animations["walk"] = [frame.copy(), frame.copy(), frame.copy()]
    return sprite


def test_frame_image_colors_and_scale():
    sprite = model.loads(SPRITE)
    image = render.frame_image(sprite, sprite.frame(), scale=3)
    assert image.size == (12, 9)
    assert image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert image.getpixel((3, 0)) == (0x1D, 0x1D, 0x2B, 255)


def test_horizontal_sheet_puts_all_frames_in_one_row():
    sheet = render.render_sheet(two_animation_sprite(), render.Layout.HORIZONTAL, 2)
    assert sheet.image.size == (4 * 8, 6)
    assert [f["x"] for f in sheet.frames["walk"]] == [8, 16, 24]


def test_grid_sheet_has_one_row_per_animation():
    sheet = render.render_sheet(two_animation_sprite(), render.Layout.GRID, 1)
    assert sheet.image.size == (12, 6)
    assert sheet.frames["idle"] == [{"x": 0, "y": 0, "w": 4, "h": 3, "duration": 100}]
    assert [(f["x"], f["y"]) for f in sheet.frames["walk"]] == [(0, 3), (4, 3), (8, 3)]


def test_import_round_trips_through_render():
    sprite = model.loads(SPRITE)
    imported = render.import_image(render.frame_image(sprite, sprite.frame()))
    again = render.frame_image(imported, imported.frame())
    assert again.tobytes() == render.frame_image(sprite, sprite.frame()).tobytes()
    assert imported.palette["a"].hex == "#1D1D2B"  # most common color first


def test_import_rejects_too_many_colors_or_large_images():
    many = Image.new("RGBA", (100, 1))
    many.putdata([(i, 0, 0, 255) for i in range(100)])
    with pytest.raises(PixelError, match="100 colors"):
        render.import_image(many)
    with pytest.raises(PixelError, match="at most 256x256"):
        render.import_image(Image.new("RGBA", (300, 10)))


def test_grid_with_coordinates_aligns_columns():
    wide = [["."] * 12]
    assert text.grid_with_coordinates(wide).splitlines() == [
        "            11",
        "  012345678901",
        "0 ............",
    ]


# --- CLI ----------------------------------------------------------------------------


def invoke(*args: str | Path):
    return runner.invoke(app, ["pixel", *map(str, args)])


@pytest.fixture
def sprite_file(tmp_path: Path) -> Path:
    path = tmp_path / "hero.pxl.toml"
    path.write_text(SPRITE)
    return path


def test_cli_new_creates_and_refuses_to_overwrite(tmp_path: Path):
    path = tmp_path / "a.pxl.toml"
    result = invoke("new", path, "--size", "8x4", "--frames", "2")
    assert result.exit_code == 0
    assert "with 2 blank frames" in result.output
    sprite = model.load(path)
    assert (sprite.width, sprite.height, len(sprite.animations["idle"])) == (8, 4, 2)
    result = invoke("new", path)
    assert result.exit_code == 1 and "--force" in result.output


def test_cli_edit_saves_and_prints_the_frame(sprite_file: Path):
    result = invoke("set", sprite_file, "k", "1,1", "2,1")
    assert result.exit_code == 0, result.output
    assert "1 kkkk" in result.output
    assert rows(model.load(sprite_file).frame())[1] == "kkkk"


def test_cli_edit_errors_leave_the_file_unchanged(sprite_file: Path):
    before = sprite_file.read_text()
    result = invoke("set", sprite_file, "z", "1,1")
    assert result.exit_code == 1 and "not in the palette" in result.output
    result = invoke("line", sprite_file, "k", "0,0", "9,9")
    assert result.exit_code == 1 and "outside" in result.output
    assert sprite_file.read_text() == before


def test_cli_ellipse_and_polygon(sprite_file: Path):
    result = invoke("ellipse", sprite_file, "s", "0,0", "3,2", "--filled")
    assert result.exit_code == 0, result.output
    assert rows(model.load(sprite_file).frame()) == [".ss.", "ssss", ".ss."]
    result = invoke("polygon", sprite_file, ".", "0,0", "3,0", "0,2", "--filled")
    assert result.exit_code == 0, result.output
    assert rows(model.load(sprite_file).frame()) == ["....", "...s", ".ss."]
    before = sprite_file.read_text()
    result = invoke("polygon", sprite_file, "k", "0,0", "3,2")
    assert result.exit_code == 1 and "at least 3 corners" in result.output
    assert sprite_file.read_text() == before


def test_cli_shift_accepts_negative_offsets(sprite_file: Path):
    result = invoke("shift", sprite_file, "--dx", "-1")
    assert result.exit_code == 0, result.output
    assert rows(model.load(sprite_file).frame()) == ["kk..", "ssk.", "kk.."]


def test_cli_frame_add_copies_and_remove(sprite_file: Path):
    assert (
        invoke("frame", "add", sprite_file, "walk", "--from", "idle:0").exit_code == 0
    )
    assert invoke("frame", "add", sprite_file, "walk").exit_code == 0  # copies last
    sprite = model.load(sprite_file)
    assert [f.layers for f in sprite.animations["walk"]] == [
        sprite.frame_at("idle").layers
    ] * 2

    assert invoke("frame", "remove", sprite_file, "walk", "0").exit_code == 0
    assert invoke("frame", "remove", sprite_file, "walk", "0").exit_code == 0
    assert "walk" not in model.load(sprite_file).animations
    result = invoke("frame", "remove", sprite_file, "idle", "0")
    assert result.exit_code == 1 and "only frame" in result.output


def test_cli_recolor_all_frames(sprite_file: Path):
    invoke("frame", "add", sprite_file, "walk", "--from", "idle:0")
    assert invoke("recolor", sprite_file, "s", ".", "--all").exit_code == 0
    sprite = model.load(sprite_file)
    assert all(
        "s" not in "".join(rows(f.layers["main"])) for f in sprite.animations["walk"]
    )
    assert "s" not in "".join(rows(sprite.frame("idle")))


def test_cli_render_sheet_writes_png_and_frame_map(sprite_file: Path):
    invoke("frame", "add", sprite_file, "walk", "--from", "idle:0")
    result = invoke("render", sprite_file, "--scale", "2", "--layout", "grid")
    assert result.exit_code == 0, result.output
    with Image.open(sprite_file.with_name("hero.png")) as image:
        assert image.size == (8, 12)
    frame_map = json.loads(sprite_file.with_name("hero.json").read_text())
    assert frame_map["layout"] == "grid"
    assert frame_map["animations"]["walk"] == [
        {"x": 0, "y": 6, "w": 8, "h": 6, "duration": 100}
    ]


def test_cli_render_single_frame_has_no_frame_map(sprite_file: Path):
    result = invoke("render", sprite_file, "-o", sprite_file.with_name("one.png"))
    assert result.exit_code == 0, result.output
    assert not sprite_file.with_name("one.json").exists()


def test_cli_import_then_show(tmp_path: Path, sprite_file: Path):
    png = tmp_path / "art.png"
    sprite = model.load(sprite_file)
    render.frame_image(sprite, sprite.frame()).save(png)
    result = invoke("import", png)
    assert result.exit_code == 0, result.output
    shown = invoke("show", tmp_path / "art.pxl.toml")
    assert "palette: . transparent | a #1D1D2B" in shown.output
    assert "1 abba" in shown.output
