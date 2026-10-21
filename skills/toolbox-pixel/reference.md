# `toolbox pixel` reference

## File format (`.pxl.toml`)

```toml
size = [16, 16]            # [WIDTH, HEIGHT], 1-256 each; every frame has this size

[palette]                  # KEY = "COLOR [optional name]"
k = "#1D1D2B outline"      # #RRGGBB
g = "#00000060 shadow"     # #RRGGBBAA for partly transparent colors

[animations.idle]          # names: letters, digits, - and _
frames = [
"""
................
...
""",                       # one triple-quoted grid per frame, HEIGHT rows of WIDTH keys
]

[animations.walk]          # animations render in file order
frames = [ """...""", """...""" ]
```

- `.` is always transparent and cannot be redefined.
- Keys are one character from `a-z A-Z 0-9`, so at most 62 colors.
- Rows may be indented; blank lines around a grid are ignored.
- Only `size`, `anchor`, `layers`, `palette` and `animations` are allowed at the top
  level.
- An animation may set `durations`: milliseconds per frame, as one number for every
  frame or a list with one number per frame. The default is 100.

### Layered sprites

```toml
size = [64, 64]
anchor = [30, 60]            # optional; X,Y inside the frame
layers = ["back", "body", "front"]   # bottom to top

[animations.standby]
durations = [140, 120]
back = [ """...""", """...""" ]    # one list per layer instead of `frames`
body = [ """...""", """...""" ]
front = [ """...""", """...""" ]
```

- Every layer lists the same number of frames; a frame is the stack of its layers.
- Layer names use letters, digits, `-` and `_`; `frames` and `durations` are reserved.
- Where layers overlap, the upper layer's pixel shows; partly transparent colors blend
  when rendered.
- A sprite without `layers` has one layer called `main`. `layer add` makes it layered.

## Commands

Every drawing command takes `FILE`, then its arguments, plus `-a/--animation NAME`
(default: the first animation), `-f/--frame INDEX` (default: 0) and `-l/--layer NAME`
(required when the sprite has several layers).

| Command | Arguments and options | Notes |
|---|---|---|
| `new FILE` | `--size WxH` (16x16), `--animation NAME` (idle), `--frames N` (1, max 64), `--layers a,b`, `--force` | Refuses to overwrite without `--force`. |
| `show FILE` | `-a`, `-f`, `-l`, `--color` | Without `-f`: every frame (of `-a` if given). Without `-l`: layers stacked. |
| `set FILE KEY X,Y...` | | Any number of points. |
| `line FILE KEY X,Y X,Y` | | Both ends included. |
| `rect FILE KEY X,Y X,Y` | `--filled` | Any two opposite corners; border only unless filled. |
| `ellipse FILE KEY X,Y X,Y` | `--filled` | The ellipse that fits the box between two opposite corners; equal sides make a circle. Border only unless filled; the border is one pixel thick and touches all four sides of the box. |
| `polygon FILE KEY X,Y X,Y X,Y...` | `--filled` | Closed shape through 3 or more corners in order; the last joins the first. Border only unless filled. Filled, where sides cross the overlap stays empty (even-odd). |
| `fill FILE KEY X,Y` | | Flood fill of the same-colored area, 4-connected. |
| `mirror FILE` | `--from left\|right\|top\|bottom` (required) | Copies that half onto the other, mirrored. Odd widths keep the middle column. |
| `flip FILE` | `-d horizontal\|vertical` (horizontal) | horizontal = face the other way. |
| `shift FILE` | `--dx N`, `--dy N`, `--wrap` | Negative values move left/up. Without `--wrap`, pixels pushed off the edge are lost. |
| `move FILE X,Y X,Y` | `--dx N`, `--dy N` | Moves the rectangle; the area it leaves turns transparent, pixels pushed off the edge are lost. |
| `copy FILE X,Y X,Y --to X,Y` | `--from A:N` or `A:N:LAYER` | Stamps the rectangle with its top-left at `--to`; transparent pixels are skipped. Source defaults to the edited frame (and layer). |
| `rotate FILE --angle DEG` | `--pivot X,Y` (frame center) | Clockwise; negative is anticlockwise. 90-degree steps are exact; other angles are smoothed RotSprite-style. Rotates the whole layer, so keep the part on its own layer. |
| `outline FILE KEY` | `--diagonal` | Colors transparent pixels touching the shape. Run once. |
| `selout FILE KEY` | `--inner` | Recolors each `KEY` pixel with the darkest palette color of the same hue as the part it borders (grays match grays). Pixels with no darker match keep `KEY`. `--inner` keeps `KEY` where it touches transparency. |
| `ramp FILE KEYS #RRGGBB` | `--name N`, `--hue-shift DEG` (20), `--force` | Adds `len(KEYS)` shades (2-9), darkest first; names them `N-1`, `N-2`... The base color is key number ⌈n/2⌉: with an even count there is one shadow fewer than highlights (`1234`: base on `2`), and 2 keys give the base plus a highlight, no shadow. Use odd counts. The darkest shade is always about 30% of the base's lightness, so fewer steps mean a bigger jump to it. One color (e.g. the outline) is not a ramp: add it to `[palette]` by hand. |
| `recolor FILE OLD NEW` | `--all` | `--all` changes every frame of every animation. |
| `frame add FILE ANIMATION` | `--from A:N`, `--blank`, `--at N` | Default copies the animation's last frame, or a blank frame for a new animation. `--from` and `--blank` cannot be combined. |
| `frame remove FILE ANIMATION N` | | Removing an animation's last frame removes the animation. |
| `frame duration FILE ANIMATION MS` | `-f N` | Every frame unless `-f`. |
| `layer add FILE NAME` | `--at N` (top) | Adds an empty layer to every frame; 0 is the bottom. |
| `layer remove FILE NAME` / `layer rename FILE OLD NEW` | | |
| `anchor FILE X,Y` | | Saved in the file and written to the .json frame map. |
| `render FILE` | `-o PNG`, `--scale N` (1-64), `--layout horizontal\|grid`, `-a`, `-f`, `--onion`, `--gif` | Default output: `NAME.png` next to the file; with several frames also a `.json` next to the PNG, `-o` included. Here `-l` is `--layout`, not a layer: `render` always stacks every layer. `-f N --onion` draws frame N-1 faintly underneath; on frame 0 it draws the animation's last frame, to check the loop. `--gif` writes one animation (`-a`, default the first) as a looping GIF, default `NAME-ANIMATION.gif`; GIFs are previews, not game assets. |
| `import IMAGE` | `-o FILE`, `-a NAME` (idle), `--force` | Max 256x256 and 62 colors; most common color gets key `a`. |

## Sprite sheets

- `--layout horizontal`: all frames in one row, animations in file order.
- `--layout grid`: one row per animation, its frames left to right; shorter rows end
  with empty space.
- With more than one frame, `render` also writes `NAME.json`:

```json
{
  "image": "hero.png",
  "frame_width": 128,
  "frame_height": 128,
  "layout": "grid",
  "anchor": {"x": 64, "y": 120},
  "animations": {
    "idle": [{"x": 0, "y": 0, "w": 128, "h": 128, "duration": 100}],
    "walk": [{"x": 0, "y": 128, "w": 128, "h": 128, "duration": 120}, "..."]
  }
}
```

Positions, sizes and the anchor are in output pixels (after `--scale`); `anchor` is
present only when the sprite sets one. `duration` is in milliseconds. Render game assets at
`--scale 1` and let the engine scale with nearest-neighbor filtering. Use a large
scale only for previews.

## Errors you may see

| Message | Fix |
|---|---|
| `'z' is not in the palette; use one of: . k s` | Add `z` to `[palette]` or use an existing key. |
| `point 16,3 is outside the 16x16 frame (x 0-15, y 0-15)` | Coordinates start at 0. |
| `a polygon needs at least 3 corners, got 2` | Give every corner, in order; use `line` for a single side. |
| `animations.walk frame 2, row 5: has 15 pixels, expected 16` | Fix that row in the file. |
| `no animation 'run'; the sprite has: idle, walk` | Check the name, or `frame add FILE run` to create it. |
| `no frame 4 in 'walk'; it has frames 0-3` | Frame indexes start at 0. |
| `the sprite has layers back, body; choose one with -l/--layer` | Pass `-l LAYER`. |
| `animations.idle: layer 'fx' has 1 frames, but 'back' has 2` | Give every layer the same number of frames. |
| `... already exists; use --force to overwrite it` | Pick another name, or pass `--force` deliberately. |

## Palette presets

Paste one under `[palette]`. Keys follow the palettes' usual 0-f numbering.

**PICO-8** (16 colors):

```toml
0 = "#000000 black"
1 = "#1D2B53 dark-blue"
2 = "#7E2553 dark-purple"
3 = "#008751 dark-green"
4 = "#AB5236 brown"
5 = "#5F574F dark-grey"
6 = "#C2C3C7 light-grey"
7 = "#FFF1E8 white"
8 = "#FF004D red"
9 = "#FFA300 orange"
a = "#FFEC27 yellow"
b = "#00E436 green"
c = "#29ADFF blue"
d = "#83769C lavender"
e = "#FF77A8 pink"
f = "#FFCCAA peach"
```

**Sweetie 16** (16 colors, by GrafxKid):

```toml
0 = "#1A1C2C black"
1 = "#5D275D purple"
2 = "#B13E53 red"
3 = "#EF7D57 orange"
4 = "#FFCD75 yellow"
5 = "#A7F070 light-green"
6 = "#38B764 green"
7 = "#257179 dark-green"
8 = "#29366F dark-blue"
9 = "#3B5DC9 blue"
a = "#41A6F6 light-blue"
b = "#73EFF7 cyan"
c = "#F4F4F4 white"
d = "#94B0C2 light-grey"
e = "#566C86 grey"
f = "#333C57 dark-grey"
```

**Game Boy** (4 greens, darkest first):

```toml
0 = "#0F380F darkest"
1 = "#306230 dark"
2 = "#8BAC0F light"
3 = "#9BBC0F lightest"
```
