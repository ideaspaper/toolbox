"""The text sprite format (``.pxl.toml``): parsing, validation and writing.

A sprite file looks like this::

    size = [4, 2]

    [palette]
    k = "#1D1D2B outline"   # one character per color, optional name after the color
    s = "#F2C9A0 skin"

    [animations.idle]
    frames = [
    \"\"\"
    .kk.
    kssk
    \"\"\",
    ]

``.`` is always transparent. Every frame of every animation has the same size and
shares the palette. Validation is strict and errors name the exact frame, row and
column, so mistakes are easy to find in the file.

A sprite can also be split into layers, drawn bottom to top, so parts such as a
weapon or a cape can be moved or redrawn on their own. Each animation then lists
the frames of every layer instead of ``frames``::

    layers = ["body", "weapon"]

    [animations.idle]
    durations = [120, 80]   # optional: milliseconds per frame (or one number)
    body = [ \"\"\"...\"\"\", \"\"\"...\"\"\" ]
    weapon = [ \"\"\"...\"\"\", \"\"\"...\"\"\" ]

An optional top-level ``anchor = [X, Y]`` marks the point the game lines frames up
on, usually between the feet.
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

TRANSPARENT = "."
MAX_SIZE = 256
SPRITE_SUFFIX = ".pxl.toml"
KEY_CHARACTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MAIN_LAYER = "main"  # the one layer of a sprite without `layers`
DEFAULT_DURATION = 100  # milliseconds per frame
_FRAMES = "frames"
_DURATIONS = "durations"
_RESERVED_LAYER_NAMES = {_FRAMES, _DURATIONS}
_NAME = re.compile(r"[A-Za-z0-9_-]+")
_COLOR = re.compile(r"#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})")
_TOP_LEVEL_KEYS = {"size", "anchor", "layers", "palette", "animations"}

Grid = list[list[str]]


class PixelError(ValueError):
    """Raised for invalid sprite files, arguments or edits."""


@dataclass(frozen=True)
class Color:
    """A palette color as ``#RRGGBB`` or ``#RRGGBBAA`` (upper-case), with a name."""

    hex: str
    name: str = ""

    @property
    def rgba(self) -> tuple[int, int, int, int]:
        digits = self.hex[1:]
        alpha = int(digits[6:8], 16) if len(digits) == 8 else 255
        return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), alpha

    @classmethod
    def parse(cls, text: str) -> "Color":
        color, _, name = text.strip().partition(" ")
        if not _COLOR.fullmatch(color):
            raise PixelError(f"invalid color {color!r}: use #RRGGBB or #RRGGBBAA")
        return cls(color.upper(), name.strip())

    def __str__(self) -> str:
        return f"{self.hex} {self.name}" if self.name else self.hex


@dataclass
class Frame:
    """One animation frame: a grid per layer, and how long it shows."""

    layers: dict[str, Grid]
    duration: int = DEFAULT_DURATION

    def copy(self) -> "Frame":
        return Frame(
            {name: [row[:] for row in grid] for name, grid in self.layers.items()},
            self.duration,
        )


@dataclass
class Sprite:
    width: int
    height: int
    palette: dict[str, Color] = field(default_factory=dict)
    animations: dict[str, list[Frame]] = field(default_factory=dict)
    layers: list[str] = field(default_factory=lambda: [MAIN_LAYER])  # bottom first
    anchor: tuple[int, int] | None = None

    @property
    def layered(self) -> bool:
        """True when the file names its layers (``layers = [...]``)."""
        return self.layers != [MAIN_LAYER]

    def animation_name(self, name: str | None) -> str:
        """``name`` if it exists, or the first animation when ``name`` is None."""
        if name is None:
            return next(iter(self.animations))
        if name not in self.animations:
            known = ", ".join(self.animations)
            raise PixelError(f"no animation {name!r}; the sprite has: {known}")
        return name

    def layer_name(self, name: str | None) -> str:
        """``name`` if it is a layer; None is only allowed with a single layer."""
        if name is None:
            if len(self.layers) == 1:
                return self.layers[0]
            raise PixelError(
                f"the sprite has layers {', '.join(self.layers)}; "
                "choose one with -l/--layer"
            )
        if name not in self.layers:
            raise PixelError(
                f"no layer {name!r}; the sprite has: {', '.join(self.layers)}"
            )
        return name

    def frame_at(self, animation: str | None = None, index: int = 0) -> Frame:
        frames = self.animations[self.animation_name(animation)]
        if not 0 <= index < len(frames):
            raise PixelError(
                f"no frame {index} in {self.animation_name(animation)!r}; "
                f"it has frames 0-{len(frames) - 1}"
            )
        return frames[index]

    def frame(
        self, animation: str | None = None, index: int = 0, layer: str | None = None
    ) -> Grid:
        """One layer's grid of a frame (the only layer when there is just one)."""
        return self.frame_at(animation, index).layers[self.layer_name(layer)]

    def composite(self, frame: Frame) -> Grid:
        """The frame's layers stacked: each pixel shows its top non-clear key."""
        result = self.blank_grid()
        for name in self.layers:
            for y, row in enumerate(frame.layers[name]):
                for x, key in enumerate(row):
                    if key != TRANSPARENT:
                        result[y][x] = key
        return result

    def check_key(self, key: str) -> str:
        """Return ``key`` if it is a palette key or ``.``; raise otherwise."""
        if key != TRANSPARENT and key not in self.palette:
            known = " ".join([TRANSPARENT, *self.palette])
            raise PixelError(f"{key!r} is not in the palette; use one of: {known}")
        return key

    def blank_grid(self) -> Grid:
        return [[TRANSPARENT] * self.width for _ in range(self.height)]

    def blank_frame(self) -> Frame:
        return Frame({name: self.blank_grid() for name in self.layers})

    def add_layer(self, name: str, index: int | None = None) -> None:
        """Add an empty layer to every frame (default: on top)."""
        check_layer_name(name)
        if name in self.layers:
            raise PixelError(f"the sprite already has a layer {name!r}")
        position = len(self.layers) if index is None else min(index, len(self.layers))
        self.layers.insert(position, name)
        for frames in self.animations.values():
            for frame in frames:
                frame.layers[name] = self.blank_grid()

    def remove_layer(self, name: str) -> None:
        self.layer_name(name)
        if len(self.layers) == 1:
            raise PixelError("cannot remove the sprite's only layer")
        self.layers.remove(name)
        for frames in self.animations.values():
            for frame in frames:
                del frame.layers[name]

    def rename_layer(self, old: str, new: str) -> None:
        self.layer_name(old)
        check_layer_name(new)
        if new in self.layers:
            raise PixelError(f"the sprite already has a layer {new!r}")
        self.layers[self.layers.index(old)] = new
        for frames in self.animations.values():
            for frame in frames:
                frame.layers[new] = frame.layers.pop(old)


def check_layer_name(name: str) -> str:
    if not _NAME.fullmatch(name):
        raise PixelError(f"layer {name!r}: names may only use letters, digits, - and _")
    if name in _RESERVED_LAYER_NAMES:
        raise PixelError(f"{name!r} is reserved and cannot name a layer")
    return name


def parse_size(text: str) -> tuple[int, int]:
    """Parse ``WIDTHxHEIGHT``."""
    width, sep, height = text.lower().partition("x")
    try:
        if not sep:
            raise ValueError
        size = int(width), int(height)
    except ValueError:
        raise PixelError(
            f"invalid size {text!r}: use WIDTHxHEIGHT, e.g. 16x16"
        ) from None
    _check_size(*size)
    return size


def parse_point(text: str) -> tuple[int, int]:
    """Parse ``X,Y`` (0-based, from the top-left)."""
    try:
        x, y = (int(part) for part in text.split(","))
    except ValueError:
        raise PixelError(f"invalid point {text!r}: use X,Y, e.g. 3,4") from None
    return x, y


def _check_size(width: int, height: int) -> None:
    if not (1 <= width <= MAX_SIZE and 1 <= height <= MAX_SIZE):
        raise PixelError(f"size must be between 1x1 and {MAX_SIZE}x{MAX_SIZE}")


def _is_pair(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, int) for item in value)
    )


def loads(text: str) -> Sprite:
    """Parse and validate a sprite file's text."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PixelError(f"not valid TOML: {exc}") from exc

    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise PixelError(
            f"unknown key(s) {', '.join(sorted(unknown))}; "
            f"expected {', '.join(sorted(_TOP_LEVEL_KEYS))}"
        )

    size = data.get("size")
    if not _is_pair(size):
        raise PixelError("size must be [WIDTH, HEIGHT], e.g. size = [16, 16]")
    _check_size(*size)
    sprite = Sprite(width=size[0], height=size[1])

    if "anchor" in data:
        anchor = data["anchor"]
        if not _is_pair(anchor):
            raise PixelError("anchor must be [X, Y], e.g. anchor = [16, 30]")
        if not (0 <= anchor[0] < sprite.width and 0 <= anchor[1] < sprite.height):
            raise PixelError(f"anchor {anchor[0]},{anchor[1]} is outside the frame")
        sprite.anchor = (anchor[0], anchor[1])

    if "layers" in data:
        layers = data["layers"]
        if not (
            isinstance(layers, list)
            and layers
            and all(isinstance(name, str) for name in layers)
        ):
            raise PixelError('layers must be a list of names, e.g. ["body", "weapon"]')
        for name in layers:
            check_layer_name(name)
        if len(set(layers)) != len(layers):
            raise PixelError("layers: each name may appear only once")
        sprite.layers = list(layers)

    palette = data.get("palette", {})
    if not isinstance(palette, dict):
        raise PixelError("palette must be a table: [palette]")
    for key, value in palette.items():
        if len(key) != 1 or key not in KEY_CHARACTERS:
            raise PixelError(
                f"palette key {key!r} must be a single letter or digit "
                f"({TRANSPARENT!r} is reserved for transparent)"
            )
        if not isinstance(value, str):
            raise PixelError(f'palette.{key} must be a string like "#1D1D2B outline"')
        try:
            sprite.palette[key] = Color.parse(value)
        except PixelError as exc:
            raise PixelError(f"palette.{key}: {exc}") from None

    animations = data.get("animations")
    if not isinstance(animations, dict) or not animations:
        raise PixelError("the sprite needs at least one [animations.NAME] table")
    for name, animation in animations.items():
        where = f"animations.{name}"
        if not _NAME.fullmatch(name):
            raise PixelError(f"{where}: names may only use letters, digits, - and _")
        if not isinstance(animation, dict):
            raise PixelError(f"{where} must be a table")
        sprite.animations[name] = _parse_animation(sprite, animation, where)
    return sprite


def _parse_animation(sprite: Sprite, animation: dict, where: str) -> list[Frame]:
    if sprite.layered:
        expected = {*sprite.layers, _DURATIONS}
        unknown = set(animation) - expected
        if unknown:
            raise PixelError(
                f"{where}: unknown key(s) {', '.join(sorted(unknown))}; "
                f"the layers are {', '.join(sprite.layers)}"
            )
        sources = {layer: (layer, animation.get(layer)) for layer in sprite.layers}
    else:
        unknown = set(animation) - {_FRAMES, _DURATIONS}
        if unknown:
            raise PixelError(
                f"{where}: unknown key(s) {', '.join(sorted(unknown))}; "
                f"expected frames (and optionally durations). To use layers, "
                f"list them at the top: layers = [...]"
            )
        sources = {MAIN_LAYER: (_FRAMES, animation.get(_FRAMES))}

    grids: dict[str, list[Grid]] = {}
    for layer, (key, frames) in sources.items():
        if not isinstance(frames, list) or not frames:
            raise PixelError(f"{where} needs {key} = [...] with at least one frame")
        label = f"{where}.{key}" if sprite.layered else where
        grids[layer] = [
            _parse_grid(sprite, frame, f"{label} frame {index}")
            for index, frame in enumerate(frames)
        ]
    count = len(next(iter(grids.values())))
    for layer, frames in grids.items():
        if len(frames) != count:
            raise PixelError(
                f"{where}: layer {layer!r} has {len(frames)} frames, but "
                f"{sprite.layers[0]!r} has {count}; every layer needs the same number"
            )

    durations = animation.get(_DURATIONS, DEFAULT_DURATION)
    if isinstance(durations, int):
        durations = [durations] * count
    if not (
        isinstance(durations, list)
        and len(durations) == count
        and all(isinstance(ms, int) and ms > 0 for ms in durations)
    ):
        raise PixelError(
            f"{where}: durations must be milliseconds per frame, either one number "
            f"or a list of {count} positive numbers"
        )
    return [
        Frame({layer: grids[layer][index] for layer in sprite.layers}, durations[index])
        for index in range(count)
    ]


def _parse_grid(sprite: Sprite, text: object, where: str) -> Grid:
    if not isinstance(text, str):
        raise PixelError(f'{where} must be a multi-line string: """ ... """')
    # Indentation and blank lines around the grid are allowed; "." marks transparent.
    rows = [line.strip() for line in text.strip().splitlines()]
    if len(rows) != sprite.height:
        raise PixelError(f"{where}: has {len(rows)} rows, expected {sprite.height}")
    for y, row in enumerate(rows):
        if len(row) != sprite.width:
            raise PixelError(
                f"{where}, row {y}: has {len(row)} pixels, expected {sprite.width}"
            )
        for x, key in enumerate(row):
            if key != TRANSPARENT and key not in sprite.palette:
                raise PixelError(
                    f"{where}, row {y}, column {x}: {key!r} is not in the palette"
                )
    return [list(row) for row in rows]


def _grid_list(grids: list[Grid]) -> list[str]:
    lines = []
    for grid in grids:
        lines += ['"""', *("".join(row) for row in grid), '""",']
    return lines


def dumps(sprite: Sprite) -> str:
    """Write ``sprite`` as sprite file text (comments in the original are not kept)."""
    lines = [f"size = [{sprite.width}, {sprite.height}]"]
    if sprite.anchor is not None:
        lines.append(f"anchor = [{sprite.anchor[0]}, {sprite.anchor[1]}]")
    if sprite.layered:
        lines.append("layers = [" + ", ".join(f'"{n}"' for n in sprite.layers) + "]")
    lines += ["", "[palette]"]
    lines += [f'{key} = "{color}"' for key, color in sprite.palette.items()]
    for name, frames in sprite.animations.items():
        lines += ["", f"[animations.{name}]"]
        durations = [frame.duration for frame in frames]
        if set(durations) != {DEFAULT_DURATION}:
            if len(set(durations)) == 1:
                lines.append(f"{_DURATIONS} = {durations[0]}")
            else:
                lines.append(f"{_DURATIONS} = [{', '.join(map(str, durations))}]")
        for layer in sprite.layers:
            key = layer if sprite.layered else _FRAMES
            lines += [f"{key} = ["]
            lines += _grid_list([frame.layers[layer] for frame in frames])
            lines.append("]")
    return "\n".join(lines) + "\n"


def load(path: Path) -> Sprite:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PixelError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        return loads(text)
    except PixelError as exc:
        raise PixelError(f"{path}: {exc}") from None


def save(path: Path, sprite: Sprite) -> None:
    try:
        path.write_text(dumps(sprite), encoding="utf-8")
    except OSError as exc:
        raise PixelError(f"cannot write {path}: {exc.strerror or exc}") from exc
