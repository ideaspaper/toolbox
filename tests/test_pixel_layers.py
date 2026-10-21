"""Layers, timing, regions, rotation, ramps and selective outlines."""

import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from toolbox.cli import app
from toolbox.pixel import color, draw, model, render
from toolbox.pixel.model import Color, PixelError

runner = CliRunner()

LAYERED = '''
size = [4, 3]
anchor = [2, 2]
layers = ["body", "sword"]

[palette]
k = "#1D1D2B outline"
s = "#F2C9A0 skin"
w = "#FFFFFF blade"

[animations.idle]
durations = [120, 80]
body = [
"""
.kk.
kssk
.kk.
""",
"""
....
.kk.
kssk
""",
]
sword = [
"""
...w
...w
....
""",
"""
w...
w...
....
""",
]
'''


def grid(*rows: str) -> model.Grid:
    return [list(row) for row in rows]


def rows(g: model.Grid) -> list[str]:
    return ["".join(row) for row in g]


def invoke(*args: str | Path):
    return runner.invoke(app, ["pixel", *map(str, args)])


@pytest.fixture
def layered_file(tmp_path: Path) -> Path:
    path = tmp_path / "hero.pxl.toml"
    path.write_text(LAYERED)
    return path


# --- format -------------------------------------------------------------------------


def test_layered_file_parses_and_round_trips():
    sprite = model.loads(LAYERED)
    assert sprite.layers == ["body", "sword"]
    assert sprite.anchor == (2, 2)
    assert [f.duration for f in sprite.animations["idle"]] == [120, 80]
    assert rows(sprite.frame("idle", 1, "sword")) == ["w...", "w...", "...."]
    assert rows(sprite.composite(sprite.frame_at())) == [".kkw", "kssw", ".kk."]
    assert model.loads(model.dumps(sprite)) == sprite


def test_single_duration_is_written_once():
    sprite = model.loads(LAYERED.replace("durations = [120, 80]", "durations = 90"))
    assert [f.duration for f in sprite.animations["idle"]] == [90, 90]
    assert "durations = 90\n" in model.dumps(sprite)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('sword = [\n"""\n...w\n...w\n....\n""",', "sword = ["), "same number"),
        (("sword = [", "blade = ["), "unknown key.*blade"),
        (("durations = [120, 80]", "durations = [120]"), "durations must be"),
        (('layers = ["body", "sword"]', 'layers = ["body", "body"]'), "only once"),
        (('layers = ["body", "sword"]', 'layers = ["frames"]'), "reserved"),
        (("anchor = [2, 2]", "anchor = [9, 2]"), "outside the frame"),
    ],
)
def test_layered_errors(change, message):
    with pytest.raises(PixelError, match=message):
        model.loads(LAYERED.replace(*change, 1))


def test_layer_is_required_when_there_are_several():
    sprite = model.loads(LAYERED)
    with pytest.raises(PixelError, match="choose one with -l"):
        sprite.frame()
    with pytest.raises(PixelError, match="no layer 'cape'"):
        sprite.frame(layer="cape")


# --- drawing ------------------------------------------------------------------------

BLANK = grid("....", "....", "....")


def test_copy_region_stamps_without_clear_pixels():
    source = grid("ab..", ".c..", "....")
    target = grid("zzzz", "zzzz", "zzzz")
    assert rows(draw.copy_region(source, (0, 0), (1, 1), target, (2, 1))) == [
        "zzzz",
        "zzab",
        "zzzc",
    ]


def test_move_region_clears_what_it_leaves():
    shape = grid("ab..", "cd..", "....")
    assert rows(draw.move_region(shape, (0, 0), (1, 0), 0, 2)) == [
        "....",
        "cd..",
        "ab..",
    ]


def test_rotate_quarter_turns_are_exact():
    arrow = grid("....", ".ab.", "....", "....")
    assert rows(draw.rotate(arrow, 90)) == ["....", "..a.", "..b.", "...."]
    assert rows(draw.rotate(arrow, 180)) == ["....", "....", ".ba.", "...."]
    assert rows(draw.rotate(draw.rotate(arrow, 90), -90)) == rows(arrow)


def test_rotate_around_a_pivot_and_small_angles_keep_colors():
    blade = grid("w...", "w...", "w...", "g...")
    swung = draw.rotate(blade, 90, pivot=(0, 3))
    assert rows(swung)[3] == "gwww"  # turned around the grip to point right
    tilted = draw.rotate(grid(".....", "..w..", "..w..", "..w..", "....."), 30)
    assert {key for row in tilted for key in row} == {".", "w"}


def test_selout_uses_a_darker_shade_of_the_neighbor():
    palette = {
        "k": Color("#000000"),
        "r": Color("#CC3333"),
        "R": Color("#661A1A"),  # darker red
        "b": Color("#3333CC"),
    }
    shape = grid("kkk", "krk", "kbk")
    result = rows(draw.selout(shape, palette, "k"))
    assert result[0][1] == "R"  # touches red only
    assert result[2][0] == "k"  # touches blue, which has no darker shade
    inner = rows(draw.selout(grid("kkk", "rkb", "rrr"), palette, "k", inner=True))
    assert inner[1][1] == "R" and inner[0] == "kkk"


def test_ramp_is_ordered_dark_to_light_with_the_base_in_the_middle():
    shades = color.ramp(Color("#E8A0B4"), 5)
    assert shades[2] == "#E8A0B4"
    lightness = [sum(Color(s).rgba[:3]) for s in shades]
    assert lightness == sorted(lightness)
    with pytest.raises(PixelError):
        color.ramp(Color("#E8A0B4"), 12)


def test_ramp_shifts_shadows_cooler_and_highlights_warmer():
    red, _, blue, _ = Color(color.ramp(Color("#808080"), 3)[0]).rgba
    assert red == blue  # gray has no hue to shift
    dark, _, light = (Color(s).rgba for s in color.ramp(Color("#40A040"), 3))
    assert dark[2] > dark[0]  # green shadow leans blue
    assert light[0] > light[2]  # green highlight leans yellow


# --- rendering ----------------------------------------------------------------------


def test_frame_image_stacks_layers():
    sprite = model.loads(LAYERED)
    image = render.frame_image(sprite, sprite.frame_at())
    assert image.getpixel((3, 0)) == (255, 255, 255, 255)  # sword over clear body
    assert image.getpixel((1, 1)) == (0xF2, 0xC9, 0xA0, 255)


def test_onion_image_shows_the_previous_frame_faintly():
    sprite = model.loads(LAYERED)
    image = render.onion_image(sprite, "idle", 1)
    assert 0 < image.getpixel((3, 0))[3] < 255  # frame 0's sword, faint
    assert image.getpixel((0, 0))[3] == 255  # frame 1's sword, solid


# --- CLI ----------------------------------------------------------------------------


def test_cli_draws_on_the_chosen_layer(layered_file: Path):
    result = invoke("set", layered_file, "w", "0,2", "-l", "body")
    assert result.exit_code == 0, result.output
    assert "layer body" in result.output
    sprite = model.load(layered_file)
    assert rows(sprite.frame("idle", 0, "body"))[2] == "wkk."
    result = invoke("set", layered_file, "w", "0,2")
    assert result.exit_code == 1 and "choose one with -l" in result.output


def test_cli_layer_add_rename_remove(tmp_path: Path):
    path = tmp_path / "a.pxl.toml"
    invoke("new", path, "--size", "4x2")
    assert invoke("layer", "add", path, "cape", "--at", "0").exit_code == 0
    assert model.load(path).layers == ["cape", "main"]
    assert invoke("layer", "rename", path, "main", "body").exit_code == 0
    assert invoke("layer", "remove", path, "cape").exit_code == 0
    assert model.load(path).layers == ["body"]
    result = invoke("layer", "remove", path, "body")
    assert result.exit_code == 1 and "only layer" in result.output


def test_cli_new_with_layers(tmp_path: Path):
    path = tmp_path / "a.pxl.toml"
    result = invoke("new", path, "--layers", "body,weapon", "--frames", "2")
    assert result.exit_code == 0, result.output
    sprite = model.load(path)
    assert sprite.layers == ["body", "weapon"]
    assert len(sprite.animations["idle"]) == 2


def test_cli_frame_add_copies_every_layer_and_duration(layered_file: Path):
    assert (
        invoke("frame", "add", layered_file, "idle", "--from", "idle:0").exit_code == 0
    )
    frames = model.load(layered_file).animations["idle"]
    assert frames[2].layers == frames[0].layers and frames[2].duration == 120


def test_cli_frame_add_refuses_blank_and_from_together(layered_file: Path):
    before = layered_file.read_text()
    result = invoke("frame", "add", layered_file, "idle", "--blank", "--from", "idle:0")
    assert result.exit_code == 1 and "not both" in result.output
    assert layered_file.read_text() == before


def test_cli_frame_duration(layered_file: Path):
    assert (
        invoke("frame", "duration", layered_file, "idle", "200", "-f", "1").exit_code
        == 0
    )
    frames = model.load(layered_file).animations["idle"]
    assert [f.duration for f in frames] == [120, 200]


def test_cli_copy_from_another_frame(layered_file: Path):
    result = invoke(
        "copy",
        layered_file,
        "0,0",
        "0,1",
        "--to",
        "1,0",
        "--from",
        "idle:1",
        "-l",
        "sword",
    )
    assert result.exit_code == 0, result.output
    assert rows(model.load(layered_file).frame("idle", 0, "sword"))[:2] == [
        ".w.w",
        ".w.w",
    ]


def test_cli_ramp_adds_named_colors(layered_file: Path):
    result = invoke("ramp", layered_file, "123", "#3B5DC9", "--name", "robe")
    assert result.exit_code == 0, result.output
    palette = model.load(layered_file).palette
    assert palette["2"] == Color("#3B5DC9", "robe-2")
    result = invoke("ramp", layered_file, "12", "#3B5DC9")
    assert result.exit_code == 1 and "--force" in result.output


def test_cli_render_writes_durations_anchor_gif_and_onion(layered_file: Path):
    result = invoke("render", layered_file, "--scale", "2")
    assert result.exit_code == 0, result.output
    frame_map = json.loads(layered_file.with_name("hero.json").read_text())
    assert frame_map["anchor"] == {"x": 4, "y": 4}
    assert [f["duration"] for f in frame_map["animations"]["idle"]] == [120, 80]

    result = invoke("render", layered_file, "--gif")
    assert result.exit_code == 0, result.output
    with Image.open(layered_file.with_name("hero-idle.gif")) as gif:
        assert gif.n_frames == 2

    onion = layered_file.with_name("onion.png")
    assert (
        invoke("render", layered_file, "-f", "1", "--onion", "-o", onion).exit_code == 0
    )
    assert invoke("render", layered_file, "--onion").exit_code == 1


def test_cli_show_stacks_layers_by_default(layered_file: Path):
    result = invoke("show", layered_file, "-f", "0")
    assert "layers (bottom to top): body, sword" in result.output
    assert "all layers" in result.output and "0 .kkw" in result.output
    result = invoke("show", layered_file, "-f", "0", "-l", "sword")
    assert "0 ...w" in result.output
