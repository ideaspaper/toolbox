# toolbox

A personal command-line toolbox, shipped as a single executable.

## Usage

```bash
toolbox qr "https://example.com"                           # print the QR code in the terminal
toolbox qr "https://example.com" -o code.png               # write a PNG
toolbox qr "hello" -o code.svg --fg navy --bg "#ffe" -e H
echo "from a pipe" | toolbox qr -o code.png                # read data from stdin
toolbox qr --help

toolbox watermark photo.jpg contract.pdf -t "CONFIDENTIAL" # tiled diagonal text
toolbox watermark *.png -i logo.png -p 60                  # centered logo, 60% opacity
toolbox watermark --help

toolbox pixelate photo.jpg                         # whole image, automatic block size
toolbox pixelate screenshot.png -r 120,40,300,60   # only the X,Y,W,H rectangle
toolbox pixelate *.jpg -b 16                       # 16x16-pixel blocks

toolbox sprite hero.png                            # 32 px sprite, up to 32 colors
toolbox sprite *.png -s 16 -c 8                    # 16 px, 8-color palette

toolbox pixel --help                               # text-based sprite editor, see below
```

Results are saved next to the originals as `<name>_watermarked.<ext>`,
`<name>_pixelated.<ext>` or `<name>_sprite.png`.
Images keep their format, EXIF and color profile where possible; PDFs keep their text
selectable because the stamp is drawn on top of each page instead of rasterizing it.

## Pixel sprites (`toolbox pixel`)

Sprites are plain-text `.pxl.toml` files, so people and agents can edit them with any
text tool and review changes in git. Every frame shares one size and palette:

```toml
size = [8, 8]

[palette]               # one letter or digit per color; "." is always transparent
k = "#1D1D2B outline"   # an optional name may follow the color
s = "#F2C9A0 skin"      # #RRGGBBAA for partly transparent colors

[animations.idle]
frames = [
"""
..kkkk..
.kssssk.
...
""",
]
```

```bash
toolbox pixel new hero.pxl.toml --size 16x16         # then add colors to [palette]
toolbox pixel rect hero.pxl.toml s 4,4 11,9 --filled # draw (X,Y from the top-left)
toolbox pixel ellipse hero.pxl.toml s 3,0 12,8 --filled    # fits the box between corners
toolbox pixel polygon hero.pxl.toml k 2,15 7,9 12,15 --filled  # closed shape, 3+ corners
toolbox pixel outline hero.pxl.toml k
toolbox pixel frame add hero.pxl.toml walk --from idle:0
toolbox pixel set hero.pxl.toml p 4,14 5,14 -a walk -f 1
toolbox pixel show hero.pxl.toml                     # grid with coordinates
toolbox pixel show hero.pxl.toml --color             # colored terminal preview
toolbox pixel render hero.pxl.toml --scale 8 --layout grid   # PNG sheet + hero.json
toolbox sprite photo.png -s 32 -c 16 && toolbox pixel import photo_sprite.png
```

Edits change the file in place and print the edited frame, so the result is visible
immediately. Errors name the exact frame, row and column. Rewriting the file drops
comments; put color names after the color instead. `render` writes a sheet with all
frames (`--layout horizontal`: one row; `grid`: one row per animation) and, for more
than one frame, a JSON map of each animation's frame positions for the game engine.

Bigger sprites can be split into layers (`layers = ["back", "body", "weapon"]`), so a
part can move on its own; frames can have their own durations and the sprite an
anchor point, both written to the JSON map:

```bash
toolbox pixel new mage.pxl.toml --size 64x64 --layers back,body,front,fx
toolbox pixel ramp mage.pxl.toml abcde "#E894AE" --name hair  # hue-shifted shades
toolbox pixel selout mage.pxl.toml k --inner -l body   # outlines in each part's hue
toolbox pixel move mage.pxl.toml 0,0 63,47 --dy 1 -f 1 -l body  # move an area
toolbox pixel rotate mage.pxl.toml --angle 30 --pivot 14,40 -f 2 -l front
toolbox pixel frame duration mage.pxl.toml idle 180 -f 0
toolbox pixel render mage.pxl.toml -f 1 --onion --scale 6 -o check.png
toolbox pixel render mage.pxl.toml --gif --scale 4     # animated preview
```

### Agent skill

`skills/toolbox-pixel/` is a Claude Code skill that teaches an agent this workflow:
the format, coordinate rules, a drawing order, animation tips and palette presets.
Install it for every project by linking it into your user skills folder, with the
`toolbox` binary on your PATH:

```bash
ln -s "$PWD/skills/toolbox-pixel" ~/.claude/skills/toolbox-pixel
ln -s "$PWD/dist/toolbox" ~/.local/bin/toolbox
```

## Development

```bash
uv sync               # create .venv and install dependencies
uv run toolbox --help # run from source
make run ARGS="qr hi" # the same, through make
make test             # pytest
make lint             # ruff check + format check
make build            # single binary at dist/toolbox (Nuitka, ~2 min)
```

Nuitka builds for the OS and CPU it runs on, so build on each target platform
(for example in a CI matrix) to get Linux or Windows binaries.

## Layout

```
src/toolbox/
├── __init__.py      # main() entry point used by `[project.scripts]`
├── __main__.py      # `python -m toolbox` and the Nuitka entry script
├── cli.py           # root Typer app; registers every command
├── imaging.py       # shared image load/save (orientation, format, metadata)
├── qr.py            # QR logic (validation + rendering), no CLI code
├── pixelate.py      # pixelation of whole images or a region
├── sprite.py        # small pixel-art sprites with a limited palette
├── pixel/
│   ├── model.py     # the .pxl.toml format: parsing, validation, writing
│   ├── draw.py      # frame edits: line, rect, ellipse, polygon, fill, ...
│   ├── render.py    # PNG frames and sprite sheets; PNG import
│   └── text.py      # coordinate grid and colored terminal preview
├── watermark/
│   ├── __init__.py  # file type detection and watermark_file()
│   ├── stamp.py     # text/image stamps and where to place them
│   ├── image.py     # raster images: compositing, format and metadata preservation
│   └── pdf.py       # PDFs: stamp embedded once, drawn over every page
└── commands/
    ├── pixel.py     # `toolbox pixel ...` command group
    ├── pixelate.py  # `toolbox pixelate`
    ├── qr.py        # `toolbox qr`: arguments, I/O, error reporting
    ├── sprite.py    # `toolbox sprite`
    └── watermark.py # `toolbox watermark`
```

## Adding a command

1. Put the logic in `src/toolbox/<feature>.py` with plain functions and its own error type.
2. Put the CLI wrapper in `src/toolbox/commands/<feature>.py` as a `command(...)` function.
3. Register it in `cli.py`: `app.command(name="<feature>")(<feature>.command)`.
4. Add tests under `tests/`.
