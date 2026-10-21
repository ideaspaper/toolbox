"""``toolbox pixel``: create and edit text-based pixel-art sprites (``.pxl.toml``).

Every command runs non-interactively. Edits change the file in place and print the
edited frame with coordinates, so the result is visible without another command.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from toolbox import imaging
from toolbox.pixel import color, draw, model, render, text
from toolbox.pixel.model import Color, Frame, Grid, PixelError, Sprite

app = typer.Typer(
    help="Create and edit text-based pixel-art sprites (.pxl.toml). Coordinates are "
    "X,Y from the top-left, starting at 0. '.' is transparent.",
    no_args_is_help=True,
)
frame_app = typer.Typer(
    help="Add or remove animation frames, or set how long they show.",
    no_args_is_help=True,
)
layer_app = typer.Typer(
    help="Add, remove or rename layers (drawn bottom to top).", no_args_is_help=True
)
app.add_typer(frame_app, name="frame")
app.add_typer(layer_app, name="layer")

SpriteFile = Annotated[
    Path, typer.Argument(help="Sprite file (.pxl.toml).", dir_okay=False)
]
Key = Annotated[str, typer.Argument(help="Palette key, or '.' for transparent.")]
Point = Annotated[str, typer.Argument(help="X,Y")]
AnimationOption = Annotated[
    str | None,
    typer.Option("--animation", "-a", help="Animation to use (default: the first)."),
]
FrameOption = Annotated[
    int, typer.Option("--frame", "-f", min=0, help="Frame index in the animation.")
]
LayerOption = Annotated[
    str | None,
    typer.Option(
        "--layer", "-l", help="Layer to edit (required when there are several)."
    ),
]


def _fail(exc: Exception) -> NoReturn:
    typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _print_frame(
    sprite: Sprite, animation: str, index: int, layer: str | None = None
) -> None:
    """Print one layer of a frame, or all layers stacked when ``layer`` is None."""
    frame = sprite.animations[animation][index]
    shown = layer or (None if sprite.layered else model.MAIN_LAYER)
    grid = frame.layers[shown] if shown else sprite.composite(frame)
    typer.echo(text.frame_title(sprite, animation, index, layer))
    typer.echo(text.grid_with_coordinates(grid))


def _edit(
    path: Path,
    animation: str | None,
    frame: int,
    layer: str | None,
    operation: Callable[[Sprite, Grid], Grid],
) -> None:
    """Load ``path``, replace one layer of a frame with ``operation``'s result,
    save, and print it."""
    try:
        sprite = model.load(path)
        name = sprite.animation_name(animation)
        layer = sprite.layer_name(layer)
        grid = sprite.frame(name, frame, layer)
        sprite.frame_at(name, frame).layers[layer] = operation(sprite, grid)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    _print_frame(sprite, name, frame, layer if sprite.layered else None)


def _image_stem(path: Path) -> str:
    name = path.name
    if name.endswith(model.SPRITE_SUFFIX):
        return name[: -len(model.SPRITE_SUFFIX)]
    return path.stem


def _refuse_overwrite(path: Path, force: bool) -> None:
    if path.exists() and not force:
        _fail(PixelError(f"{path} already exists; use --force to overwrite it"))


def _parse_source(source: str) -> tuple[str, int, str | None]:
    """``ANIMATION:INDEX`` or ``ANIMATION:INDEX:LAYER``."""
    name, _, rest = source.partition(":")
    index, _, layer = rest.partition(":")
    if not index.isdigit():
        raise PixelError(
            f"invalid --from {source!r}: use ANIMATION:INDEX or ANIMATION:INDEX:LAYER"
        )
    return name, int(index), layer or None


@app.command()
def new(
    path: SpriteFile,
    size: Annotated[
        str, typer.Option("--size", "-s", help="Frame size as WIDTHxHEIGHT.")
    ] = "16x16",
    animation: Annotated[
        str, typer.Option("--animation", "-a", help="Name of the first animation.")
    ] = "idle",
    frames: Annotated[
        int, typer.Option("--frames", min=1, max=64, help="Number of blank frames.")
    ] = 1,
    layers: Annotated[
        str | None,
        typer.Option(
            "--layers",
            help="Comma-separated layer names, bottom first, e.g. "
            "cape,body,hair,weapon.",
        ),
    ] = None,
    force: Annotated[bool, typer.Option(help="Overwrite an existing file.")] = False,
) -> None:
    """Create a blank sprite, then add colors to the palette table in the file."""
    _refuse_overwrite(path, force)
    try:
        width, height = model.parse_size(size)
        sprite = Sprite(width, height)
        if layers:
            sprite.layers = [name.strip() for name in layers.split(",")]
        sprite.animations[animation] = [sprite.blank_frame() for _ in range(frames)]
        model.save(path, model.loads(model.dumps(sprite)))  # validates the names
    except PixelError as exc:
        _fail(exc)
    typer.echo(
        f"Created {path} ({width}x{height}, animation {animation!r} "
        f"with {frames} blank frame{'s' if frames > 1 else ''}"
        + (f", layers {', '.join(sprite.layers)})" if sprite.layered else ")")
    )


@app.command()
def show(
    path: SpriteFile,
    animation: AnimationOption = None,
    frame: Annotated[
        int | None,
        typer.Option("--frame", "-f", min=0, help="Only this frame (default: all)."),
    ] = None,
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Only this layer (default: all, stacked)."),
    ] = None,
    color_preview: Annotated[
        bool, typer.Option("--color", help="Colored preview instead of the grid.")
    ] = False,
) -> None:
    """Print the palette and frames with X/Y coordinates (default: every frame)."""
    try:
        sprite = model.load(path)
        if layer is not None:
            sprite.layer_name(layer)
        if frame is not None:  # one frame of one animation (default: the first)
            name = sprite.animation_name(animation)
            sprite.frame_at(name, frame)
            selected = [(name, frame)]
        else:
            names = (
                [sprite.animation_name(animation)] if animation else sprite.animations
            )
            selected = [
                (name, index)
                for name in names
                for index in range(len(sprite.animations[name]))
            ]
    except PixelError as exc:
        _fail(exc)
    typer.echo(text.palette_legend(sprite))
    for name, index in selected:
        typer.echo("")
        if color_preview:
            shown = sprite.animations[name][index]
            grid = shown.layers[layer] if layer else sprite.composite(shown)
            typer.echo(text.frame_title(sprite, name, index, layer))
            typer.echo(text.colored_preview(sprite, grid))
        else:
            _print_frame(sprite, name, index, layer)


@app.command(name="render")
def render_command(
    path: SpriteFile,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="PNG to write (default: next to the file)."
        ),
    ] = None,
    scale: Annotated[
        int,
        typer.Option(
            "--scale", min=1, max=render.MAX_SCALE, help="Enlarge each pixel N times."
        ),
    ] = 1,
    layout: Annotated[
        render.Layout,
        typer.Option(
            "--layout", "-l", help="Sprite sheet: one row, or one row per animation."
        ),
    ] = render.Layout.HORIZONTAL,
    animation: Annotated[
        str | None,
        typer.Option("--animation", "-a", help="Only this animation."),
    ] = None,
    frame: Annotated[
        int | None,
        typer.Option("--frame", "-f", min=0, help="Only this frame of the animation."),
    ] = None,
    onion: Annotated[
        bool,
        typer.Option(
            help="With --frame: draw the previous frame faintly underneath, to "
            "check the motion between them."
        ),
    ] = False,
    gif: Annotated[
        bool,
        typer.Option(
            "--gif",
            help="Write the animation (default: the first) as a looping GIF "
            "timed by the frame durations, for previewing.",
        ),
    ] = False,
) -> None:
    """Render to PNG. Several frames become a sprite sheet plus a .json frame map."""
    try:
        sprite = model.load(path)
        if gif:
            name = sprite.animation_name(animation)
            output = output or path.with_name(f"{_image_stem(path)}-{name}.gif")
            render.save_animation(sprite, name, output, scale)
            typer.echo(
                f"Saved {output} ({len(sprite.animations[name])} frames, "
                f"{sprite.width * scale}x{sprite.height * scale})"
            )
            return
        output = output or path.with_name(_image_stem(path) + ".png")
        if onion and frame is None:
            raise PixelError("--onion needs --frame")
        if frame is not None:
            name = sprite.animation_name(animation)
            selected = sprite.frame_at(name, frame)
            image = (
                render.onion_image(sprite, name, frame, scale)
                if onion
                else render.frame_image(sprite, selected, scale)
            )
            frames = None
        else:
            names = [sprite.animation_name(animation)] if animation else None
            sheet = render.render_sheet(sprite, layout, scale, names)
            image, frames = sheet.image, sheet.frames
        image.save(output, format="PNG")
    except PixelError as exc:
        _fail(exc)
    except OSError as exc:
        _fail(PixelError(f"cannot write {output}: {exc.strerror or exc}"))
    typer.echo(f"Saved {output} ({image.width}x{image.height})")

    if frames and sum(len(positions) for positions in frames.values()) > 1:
        frame_map = output.with_suffix(".json")
        data = {
            "image": output.name,
            "frame_width": sprite.width * scale,
            "frame_height": sprite.height * scale,
            "layout": layout.value,
        }
        if sprite.anchor is not None:
            data["anchor"] = {
                "x": sprite.anchor[0] * scale,
                "y": sprite.anchor[1] * scale,
            }
        data["animations"] = frames
        frame_map.write_text(json.dumps(data, indent=2) + "\n")
        typer.echo(f"Saved {frame_map}")


@app.command(name="import")
def import_command(
    image: Annotated[
        Path,
        typer.Argument(
            help="Image to import, e.g. from `toolbox sprite`.",
            exists=True,
            dir_okay=False,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Sprite file (default: next to the image)."
        ),
    ] = None,
    animation: Annotated[
        str, typer.Option("--animation", "-a", help="Animation name for the frame.")
    ] = "idle",
    force: Annotated[bool, typer.Option(help="Overwrite an existing file.")] = False,
) -> None:
    """Turn a small image into an editable sprite file."""
    output = output or image.with_name(image.stem + model.SPRITE_SUFFIX)
    _refuse_overwrite(output, force)
    try:
        loaded, _ = imaging.load(image)
        sprite = render.import_image(loaded, animation)
        model.save(output, model.loads(model.dumps(sprite)))  # validates the name
    except (PixelError, imaging.ImageError) as exc:
        _fail(exc)
    typer.echo(f"Created {output} ({len(sprite.palette)} colors)")
    _print_frame(sprite, animation, 0)


@app.command(name="set")
def set_command(
    path: SpriteFile,
    key: Key,
    points: Annotated[list[str], typer.Argument(help="One or more X,Y points.")],
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Set individual pixels."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.set_pixels(
            grid, [model.parse_point(point) for point in points], sprite.check_key(key)
        ),
    )


@app.command()
def line(
    path: SpriteFile,
    key: Key,
    start: Point,
    end: Point,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Draw a 1-pixel line; both ends included."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.line(
            grid,
            model.parse_point(start),
            model.parse_point(end),
            sprite.check_key(key),
        ),
    )


@app.command()
def rect(
    path: SpriteFile,
    key: Key,
    corner: Annotated[str, typer.Argument(help="X,Y of one corner.")],
    opposite: Annotated[str, typer.Argument(help="X,Y of the opposite corner.")],
    filled: Annotated[bool, typer.Option(help="Fill the inside too.")] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Draw a rectangle between two corners (border only unless --filled)."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.rect(
            grid,
            model.parse_point(corner),
            model.parse_point(opposite),
            sprite.check_key(key),
            filled,
        ),
    )


@app.command()
def ellipse(
    path: SpriteFile,
    key: Key,
    corner: Annotated[str, typer.Argument(help="X,Y of one corner of the box.")],
    opposite: Annotated[str, typer.Argument(help="X,Y of the opposite corner.")],
    filled: Annotated[bool, typer.Option(help="Fill the inside too.")] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Draw an ellipse or circle that fits the box between two corners."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.ellipse(
            grid,
            model.parse_point(corner),
            model.parse_point(opposite),
            sprite.check_key(key),
            filled,
        ),
    )


@app.command()
def polygon(
    path: SpriteFile,
    key: Key,
    corners: Annotated[
        list[str], typer.Argument(help="Three or more X,Y corners, in order.")
    ],
    filled: Annotated[bool, typer.Option(help="Fill the inside too.")] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Draw a closed shape through the corners (border only unless --filled)."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.polygon(
            grid,
            [model.parse_point(corner) for corner in corners],
            sprite.check_key(key),
            filled,
        ),
    )


@app.command()
def fill(
    path: SpriteFile,
    key: Key,
    point: Annotated[str, typer.Argument(help="X,Y inside the area to fill.")],
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Flood-fill the same-colored area around a point."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.fill(
            grid, model.parse_point(point), sprite.check_key(key)
        ),
    )


@app.command()
def mirror(
    path: SpriteFile,
    source: Annotated[
        draw.Side,
        typer.Option("--from", help="Half to copy onto the other half, mirrored."),
    ],
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Make the frame symmetric by mirroring one half onto the other."""
    _edit(path, animation, frame, layer, lambda _, grid: draw.mirror(grid, source))


@app.command()
def flip(
    path: SpriteFile,
    direction: Annotated[
        draw.Direction,
        typer.Option(
            "--direction",
            "-d",
            help="horizontal swaps left and right (face the other way); "
            "vertical swaps top and bottom.",
        ),
    ] = draw.Direction.HORIZONTAL,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Flip the frame."""
    _edit(path, animation, frame, layer, lambda _, grid: draw.flip(grid, direction))


@app.command()
def shift(
    path: SpriteFile,
    dx: Annotated[
        int, typer.Option("--dx", help="Pixels to move right (< 0: left).")
    ] = 0,
    dy: Annotated[int, typer.Option("--dy", help="Pixels to move down (< 0: up).")] = 0,
    wrap: Annotated[
        bool, typer.Option(help="Wrap pixels around instead of dropping them.")
    ] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Move every pixel of the frame."""
    _edit(path, animation, frame, layer, lambda _, grid: draw.shift(grid, dx, dy, wrap))


@app.command()
def move(
    path: SpriteFile,
    corner: Annotated[str, typer.Argument(help="X,Y of one corner of the area.")],
    opposite: Annotated[str, typer.Argument(help="X,Y of the opposite corner.")],
    dx: Annotated[
        int, typer.Option("--dx", help="Pixels to move right (< 0: left).")
    ] = 0,
    dy: Annotated[int, typer.Option("--dy", help="Pixels to move down (< 0: up).")] = 0,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Move a rectangular area, e.g. the upper body one pixel down for breathing."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda _, grid: draw.move_region(
            grid, model.parse_point(corner), model.parse_point(opposite), dx, dy
        ),
    )


@app.command()
def copy(
    path: SpriteFile,
    corner: Annotated[str, typer.Argument(help="X,Y of one corner of the area.")],
    opposite: Annotated[str, typer.Argument(help="X,Y of the opposite corner.")],
    to: Annotated[
        str, typer.Option("--to", help="X,Y where the area's top-left corner lands.")
    ],
    source: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Copy from this frame, as ANIMATION:INDEX or ANIMATION:INDEX:LAYER "
            "(default: the frame being edited).",
        ),
    ] = None,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Stamp a rectangular area onto the frame; clear source pixels are skipped."""

    def operation(sprite: Sprite, grid: Grid) -> Grid:
        source_grid = grid
        if source is not None:
            name, index, source_layer = _parse_source(source)
            source_grid = sprite.frame(name, index, source_layer or layer)
        return draw.copy_region(
            source_grid,
            model.parse_point(corner),
            model.parse_point(opposite),
            grid,
            model.parse_point(to),
        )

    _edit(path, animation, frame, layer, operation)


@app.command()
def rotate(
    path: SpriteFile,
    angle: Annotated[
        float, typer.Option("--angle", help="Degrees clockwise (< 0: anticlockwise).")
    ],
    pivot: Annotated[
        str | None,
        typer.Option(
            "--pivot",
            help="X,Y of the pixel to turn around, e.g. a weapon's grip "
            "(default: the frame's center).",
        ),
    ] = None,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Rotate a layer, e.g. swing a weapon around its grip. Best on its own layer."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda _, grid: draw.rotate(
            grid, angle, model.parse_point(pivot) if pivot else None
        ),
    )


@app.command()
def outline(
    path: SpriteFile,
    key: Key,
    diagonal: Annotated[
        bool, typer.Option(help="Also outline diagonal corners (thicker look).")
    ] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Draw an outline around the shape, on the transparent pixels touching it."""
    _edit(
        path,
        animation,
        frame,
        layer,
        lambda sprite, grid: draw.outline(grid, sprite.check_key(key), diagonal),
    )


@app.command()
def selout(
    path: SpriteFile,
    key: Annotated[str, typer.Argument(help="The outline's palette key.")],
    inner: Annotated[
        bool,
        typer.Option(
            help="Keep KEY where the outline touches transparency, so only the "
            "lines inside the sprite change."
        ),
    ] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Recolor outline pixels with a darker shade of the color each one borders."""

    def operation(sprite: Sprite, grid: Grid) -> Grid:
        if key == model.TRANSPARENT:
            raise PixelError("the outline key must be a palette color")
        return draw.selout(grid, sprite.palette, sprite.check_key(key), inner)

    _edit(path, animation, frame, layer, operation)


@app.command()
def recolor(
    path: SpriteFile,
    old: Annotated[str, typer.Argument(help="Palette key to replace.")],
    new: Annotated[str, typer.Argument(help="Palette key to use instead.")],
    all_frames: Annotated[
        bool,
        typer.Option("--all", help="Every layer of every frame of every animation."),
    ] = False,
    animation: AnimationOption = None,
    frame: FrameOption = 0,
    layer: LayerOption = None,
) -> None:
    """Replace one color with another."""
    if not all_frames:
        _edit(
            path,
            animation,
            frame,
            layer,
            lambda sprite, grid: draw.recolor(
                grid, sprite.check_key(old), sprite.check_key(new)
            ),
        )
        return
    try:
        sprite = model.load(path)
        sprite.check_key(old)
        sprite.check_key(new)
        for frames in sprite.animations.values():
            for each in frames:
                for name, grid in each.layers.items():
                    each.layers[name] = draw.recolor(grid, old, new)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    count = sum(len(frames) for frames in sprite.animations.values())
    typer.echo(f"Recolored {old!r} to {new!r} in {count} frames of {path}")


@app.command()
def ramp(
    path: SpriteFile,
    keys: Annotated[
        str,
        typer.Argument(
            help="Palette keys for the shades, darkest first, e.g. 12345. The base "
            "color goes in the middle."
        ),
    ],
    base: Annotated[str, typer.Argument(help="The material's main color, #RRGGBB.")],
    name: Annotated[
        str, typer.Option("--name", help="Name for the colors, e.g. hair.")
    ] = "",
    hue_shift: Annotated[
        float,
        typer.Option(
            "--hue-shift",
            min=0,
            max=60,
            help="Degrees the darkest shade turns toward blue and the lightest "
            "toward yellow.",
        ),
    ] = 20.0,
    force: Annotated[
        bool, typer.Option(help="Replace keys that are already in the palette.")
    ] = False,
) -> None:
    """Add a hue-shifted ramp of shades (shadow to highlight) to the palette."""
    try:
        sprite = model.load(path)
        if len(set(keys)) != len(keys):
            raise PixelError(f"{keys!r} repeats a key")
        for key in keys:
            if key not in model.KEY_CHARACTERS:
                raise PixelError(f"palette key {key!r} must be a letter or digit")
        taken = [key for key in keys if key in sprite.palette]
        if taken and not force:
            raise PixelError(
                f"{' '.join(taken)} already in the palette; use --force to replace"
            )
        shades = color.ramp(Color.parse(base), len(keys), hue_shift)
        for index, (key, shade) in enumerate(zip(keys, shades, strict=True)):
            label = f"{name}-{index + 1}" if name else ""
            sprite.palette[key] = Color(shade, label)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    typer.echo(f"Added to {path}, darkest first:")
    for key in keys:
        typer.echo(f'{key} = "{sprite.palette[key]}"')


@app.command()
def anchor(
    path: SpriteFile,
    point: Annotated[
        str, typer.Argument(help="X,Y the game lines frames up on, e.g. the feet.")
    ],
) -> None:
    """Set the anchor point written to the sprite sheet's .json frame map."""
    try:
        sprite = model.load(path)
        x, y = model.parse_point(point)
        if not (0 <= x < sprite.width and 0 <= y < sprite.height):
            raise PixelError(f"anchor {x},{y} is outside the frame")
        sprite.anchor = (x, y)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    typer.echo(f"Anchor of {path} set to {x},{y}")


@frame_app.command("add")
def frame_add(
    path: SpriteFile,
    animation: Annotated[
        str, typer.Argument(help="Animation to add to (created if new).")
    ],
    source: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Copy this frame (all its layers), as ANIMATION:INDEX. Default: "
            "the animation's last frame, or a blank frame for a new animation.",
        ),
    ] = None,
    blank: Annotated[bool, typer.Option(help="Add a blank frame.")] = False,
    position: Annotated[
        int | None,
        typer.Option("--at", min=0, help="Insert at this index (default: the end)."),
    ] = None,
) -> None:
    """Add a frame, copying an existing one as a starting point."""
    try:
        sprite = model.load(path)
        frames = sprite.animations.get(animation, [])
        if blank and source is not None:
            raise PixelError("use either --blank or --from, not both")
        if blank:
            added = sprite.blank_frame()
        elif source is not None:
            name, index, source_layer = _parse_source(source)
            if source_layer is not None:
                raise PixelError("frame add copies whole frames; use ANIMATION:INDEX")
            added = sprite.frame_at(name, index).copy()
        elif frames:
            added = frames[-1].copy()
        else:
            added = sprite.blank_frame()
        index = len(frames) if position is None else min(position, len(frames))
        frames.insert(index, added)
        sprite.animations[animation] = frames
        model.save(path, model.loads(model.dumps(sprite)))  # validates a new name
    except PixelError as exc:
        _fail(exc)
    _print_frame(sprite, animation, index)


@frame_app.command("remove")
def frame_remove(
    path: SpriteFile,
    animation: Annotated[str, typer.Argument(help="Animation to remove from.")],
    index: Annotated[int, typer.Argument(min=0, help="Frame index to remove.")],
) -> None:
    """Remove a frame; removing an animation's last frame removes the animation."""
    try:
        sprite = model.load(path)
        sprite.frame_at(animation, index)
        frames = sprite.animations[animation]
        if len(frames) == 1 and len(sprite.animations) == 1:
            raise PixelError("cannot remove the sprite's only frame")
        del frames[index]
        if not frames:
            del sprite.animations[animation]
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    left = len(sprite.animations.get(animation, []))
    typer.echo(f"Removed frame {index} of {animation!r}; {left} frame(s) left")


@frame_app.command("duration")
def frame_duration(
    path: SpriteFile,
    animation: Annotated[str, typer.Argument(help="Animation to time.")],
    milliseconds: Annotated[
        int, typer.Argument(min=1, help="How long the frame shows, in ms.")
    ],
    index: Annotated[
        int | None,
        typer.Option("--frame", "-f", min=0, help="Only this frame (default: all)."),
    ] = None,
) -> None:
    """Set how long frames show, e.g. hold a wind-up pose longer."""
    try:
        sprite = model.load(path)
        frames: list[Frame] = (
            [sprite.frame_at(animation, index)]
            if index is not None
            else sprite.animations[sprite.animation_name(animation)]
        )
        for each in frames:
            each.duration = milliseconds
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    which = f"frame {index}" if index is not None else "every frame"
    typer.echo(f"{which} of {animation!r} now shows for {milliseconds} ms")


@layer_app.command("add")
def layer_add(
    path: SpriteFile,
    name: Annotated[str, typer.Argument(help="New layer's name, e.g. weapon.")],
    position: Annotated[
        int | None,
        typer.Option("--at", min=0, help="Stack position, 0 = bottom (default: top)."),
    ] = None,
) -> None:
    """Add an empty layer to every frame. A sprite's first extra layer turns its
    existing pixels into a layer named 'main'."""
    try:
        sprite = model.load(path)
        sprite.add_layer(name, position)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    typer.echo(f"Layers of {path}, bottom to top: {', '.join(sprite.layers)}")


@layer_app.command("remove")
def layer_remove(
    path: SpriteFile,
    name: Annotated[str, typer.Argument(help="Layer to remove, in every frame.")],
) -> None:
    """Remove a layer and its pixels from every frame."""
    try:
        sprite = model.load(path)
        sprite.remove_layer(name)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    typer.echo(f"Layers of {path}, bottom to top: {', '.join(sprite.layers)}")


@layer_app.command("rename")
def layer_rename(
    path: SpriteFile,
    old: Annotated[str, typer.Argument(help="Current name.")],
    new: Annotated[str, typer.Argument(help="New name.")],
) -> None:
    """Rename a layer."""
    try:
        sprite = model.load(path)
        sprite.rename_layer(old, new)
        model.save(path, sprite)
    except PixelError as exc:
        _fail(exc)
    typer.echo(f"Layers of {path}, bottom to top: {', '.join(sprite.layers)}")
