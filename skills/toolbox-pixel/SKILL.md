---
name: toolbox-pixel
description: Create, edit and animate pixel-art game sprites (characters, items, icons, tiles) and export sprite sheets with the `toolbox pixel` CLI, which stores sprites as editable text files (.pxl.toml). Use when asked to draw, make, design, edit or animate a sprite, pixel art, game icon, tile or character; to make an idle/walk/attack animation; to make detailed side-view battle sprites in the style of mobile JRPGs such as Final Fantasy Brave Exvius; to convert an image into pixel art; or to export a sprite sheet for a game engine such as Godot, Unity or Phaser.
---

# Pixel art with `toolbox pixel`

Sprites are plain-text `.pxl.toml` files: a palette of one-character color keys and
one text grid per animation frame. You can read and write the art directly, edit it
with CLI commands, and render it to PNG sprite sheets.

If `toolbox` is not found, tell the user. It is built from `~/personal/toolbox` with
`make build` (binary at `dist/toolbox`) and put on the PATH with
`ln -s ~/personal/toolbox/dist/toolbox ~/.local/bin/toolbox`.

## The file format

```toml
size = [8, 4]                 # [WIDTH, HEIGHT]; every frame has this size

[palette]                     # one letter or digit per color, optional name after it
k = "#1D1D2B outline"
s = "#F2C9A0 skin"

[animations.idle]             # one table per animation, in playback order
frames = [
"""
..kkkk..
.kssssk.
.kssssk.
..kkkk..
""",
"""
........
..kkkk..
.kssssk.
..kkkk..
""",
]
```

## The rules that matter

- **Coordinates are `X,Y`**, 0-based from the **top-left**: X is the column, Y the row.
  Every grid the CLI prints has column numbers on top and row numbers on the left.
- **`.` is transparent.** Palette keys are single letters or digits (`a-z A-Z 0-9`).
  Colors are `#RRGGBB`, or `#RRGGBBAA` for partly transparent ones.
- **Each edit command rewrites the file and prints the edited frame.** Read that
  output instead of running `show` again. A failed command leaves the file untouched
  and names the exact problem (frame, row, column).
- **Drawing commands edit the first animation's frame 0 unless told otherwise.**
  Once a sprite has several animations or frames, always pass `-a ANIMATION -f INDEX`.
  (`show` and `render` cover every frame by default.)
- **The CLI drops TOML comments** when it rewrites a file. Put color names after the
  color instead: `k = "#1D1D2B outline"`.
- **Layered sprites need `-l LAYER`** on every drawing command. `show` and `render`
  stack all layers unless you pass `-l` to `show`.
- **`render -l` means `--layout`, not layer.** `render` cannot draw a single layer;
  use `show -l LAYER` (or `--color`) to look at one.

## Layers

For anything bigger than about 32x32, or anything with a weapon, cape or effect that
moves on its own, split the sprite into layers, listed bottom to top:

```toml
size = [64, 64]
anchor = [30, 60]                  # optional: where the game lines frames up (the feet)
layers = ["back", "body", "front", "fx"]

[animations.standby]
durations = [140, 120, 140, 120]   # optional: ms per frame, or one number for all
back = [ """...""", ... ]          # one list per layer, the same number of frames each
body = [ ... ]
front = [ ... ]
fx = [ ... ]
```

Create one with `new FILE --size 64x64 --layers back,body,front,fx`, or turn a plain
sprite into a layered one with `layer add` (its pixels become the layer `main`).
Then a weapon swing is `rotate -l front --angle 30 --pivot X,Y` on one layer, and
breathing is `move` on the body's upper half, while everything else stays put.

## Two ways to draw

**Write the file directly.** This is the fastest route for small sprites (up to about
16x16) and for frames you can design in your head. Run
`toolbox pixel new FILE --size WxH --frames N` to get a valid skeleton, replace the
palette and grids with your file tools, then run `toolbox pixel show FILE`: it
validates the file and prints every frame with coordinates. Count carefully: every row
needs exactly WIDTH characters.

**Use commands.** These suit larger sprites, precise geometry and repetitive changes:
shapes (`rect`, `ellipse`, `polygon`, `line`, `fill`), symmetry (`mirror`, `flip`),
movement (`shift`), outlines (`outline`) and frames copied from frames
(`frame add --from`). Commands avoid counting mistakes and print the result after
every step.

Build curved sprites from shapes: `ellipse --filled` for round parts (heads, bodies,
eyes, orbs, coins) and `polygon --filled` for pointed or tapering ones (wings, horns,
tails, spikes, flames, blades). Fill each part in its base color, largest first, and
run `outline` once at the end. Without `--filled`, `ellipse` and `polygon` draw their
border inside the shape's box, while `outline` adds a line outside the shape.

Mixing both works well: write a rough grid, then refine it with commands, or the
other way round.

## Workflow

1. **Plan.** Settle the size (see table), a palette of 4-16 colors, the parts of the
   sprite with rough coordinates, and the frames per animation. For a game, keep every
   sprite the same size and on the same palette.
2. **Draw frame 0.** Do the silhouette first, largest parts first, then details. For
   a front-facing symmetric sprite, draw one half and run `mirror --from left`.
3. **Outline it once**, with `outline k` or by hand. Running `outline` on a shape that
   already has an outline makes the line two pixels thick.
4. **Check it at a readable size.** Render a preview to a separate file,
   `toolbox pixel render FILE -o /tmp/preview.png --scale 8`, and look at it if you
   can view images. Pixel art reads very differently from the text grid. (With
   several frames this also writes `/tmp/preview.json`; ignore it.)
5. **Animate.** `frame add FILE ANIMATION` copies the animation's last frame (or
   `--from A:N` copies any frame), so you change only what moves.
6. **Export at the game's scale**, normally 1: `toolbox pixel render FILE --layout
   horizontal|grid`. By default this writes `NAME.png` next to `NAME.pxl.toml`. With
   more than one frame it also writes `NAME.json`, which maps every frame's position.
   The JSON uses output pixels: after `--scale 8`, frames are 8 times larger. So never
   export with a preview scale, and never write a preview over the export.

## Sizes

| Asset | Typical size |
|---|---|
| Item, pickup, small icon | 8x8 or 16x16 |
| Tile | 16x16 (match the game's tile grid) |
| Character, small enemy | 16x16, 16x24 or 32x32 |
| Large enemy, boss | 32x32 to 64x64 |
| Detailed side-view battle sprite (mobile JRPG style) | 64x64, or 80x80 to 96x96 with a big weapon; see [styles/ffbe.md](styles/ffbe.md) |

## Craft tips

- **Silhouette first:** the sprite should be recognizable as a solid shape. Make
  heads and key features large; a game character's head is often a third of its height.
- **Few colors, used deliberately:** per material use a base color, a shadow and
  maybe a highlight. Pick one light direction (usually top-left) and shade the
  opposite side.
- **Outline with a dark color of the sprite's hue,** not pure black, unless the style
  calls for black.
- **Clean lines:** avoid stray single pixels and "L" corners (doubled pixels) in
  one-pixel outlines and curves.
- **Symmetry on even widths:** on a 16-wide sprite the center falls between x=7
  and x=8, so a feature at x=n mirrors to x=15-n. `mirror --from left` does this for you.
- **Animate small:** a 1-pixel change reads as motion at sprite scale.
  - **Keep the baseline fixed:** the bottom row stays on the same Y in every frame, so
    the sprite does not jitter in game.
  - **Squash and stretch** blobs and bounces: on the same baseline, make the shape
    wider and shorter (squash) or narrower and taller (stretch), widening equally on
    both sides.
  - **Walk cycles** can alternate neutral and stride frames; for a symmetric
    front view, make the second stride by `flip`ping the first (see examples.md).

## Commands

| Need | Command |
|---|---|
| New sprite | `toolbox pixel new FILE --size WxH [--animation idle] [--frames N (max 64)] [--layers a,b,c]` |
| See it | `toolbox pixel show FILE [-a A] [-f N] [-l L]`; `--color` for a terminal preview |
| Pixels | `set FILE KEY X,Y [X,Y ...]` |
| Shapes | `line FILE KEY X,Y X,Y`; `rect FILE KEY X,Y X,Y [--filled]`; `ellipse FILE KEY X,Y X,Y [--filled]`; `polygon FILE KEY X,Y X,Y X,Y [...] [--filled]`; `fill FILE KEY X,Y` |
| Symmetry and movement | `mirror FILE --from left`; `flip FILE [-d horizontal]`; `shift FILE --dx N --dy N [--wrap]` |
| Areas | `move FILE X,Y X,Y --dx N --dy N`; `copy FILE X,Y X,Y --to X,Y [--from A:N[:LAYER]]` |
| Rotation | `rotate FILE --angle DEG [--pivot X,Y]` (clockwise; clean at any angle) |
| Color | `outline FILE KEY [--diagonal]`; `selout FILE KEY [--inner]`; `recolor FILE OLD NEW [--all]` |
| Palette | `ramp FILE KEYS #RRGGBB [--name N] [--hue-shift 20]`: 2-9 hue-shifted shades, darkest first; the base lands on key number ⌈n/2⌉, so use an odd count (`12345`: base on `3`). Single colors (e.g. the outline) go in `[palette]` by hand |
| Layers | `layer add FILE NAME [--at N]`; `layer remove FILE NAME`; `layer rename FILE OLD NEW` |
| Frames | `frame add FILE ANIMATION [--from A:N] [--blank] [--at N]`; `frame remove FILE ANIMATION N`; `frame duration FILE ANIMATION MS [-f N]` |
| Anchor | `anchor FILE X,Y` (written to the .json frame map) |
| Export | `render FILE [-o out.png] [--scale N] [--layout horizontal\|grid] [-a A] [-f N]` (here `-l` is `--layout`) |
| Preview motion | `render FILE -f N --onion --scale 4 -o /tmp/x.png`; `render FILE --gif -a A --scale 4` |
| From an image | `toolbox sprite IMG -s 32 -c 16`, then `toolbox pixel import IMG_sprite.png` |

Drawing commands take `-a ANIMATION -f INDEX -l LAYER`. Erase by drawing with `.`.

## More

- [reference.md](reference.md): every option, the JSON frame map, error messages, palette presets (PICO-8, Sweetie 16, Game Boy).
- [styles/ffbe.md](styles/ffbe.md): detailed side-view battle sprites in the style of
  mobile JRPGs like Final Fantasy Brave Exvius (proportions, palettes, layers, the
  battle animation set). Read it whenever the user names that style.
- [examples.md](examples.md): a coin written as text with a second frame drawn by commands, and a character with idle and walk animations.

When you finish, tell the user which files you created (the `.pxl.toml` source and
any rendered PNG and JSON) and describe the result.
