# Worked examples

Each example was run as written. Grids show the result.

## 1. Spinning coin (8x8, written as text, second frame drawn with commands)

For small sprites, write the first frame straight into the file:

```toml
size = [8, 8]

[palette]
k = "#5A3A0E outline"
y = "#F7C531 gold"
l = "#FFF2A8 highlight"
d = "#C98A1B shadow"

[animations.spin]
frames = [
"""
..kkkk..
.kyyyyk.
kyllyydk
kylyyydk
kyyyyydk
kyyyyddk
.kddddk.
..kkkk..
""",
]
```

The highlight is top-left and the shadow bottom-right, so light comes from the top-left.
Add a second frame showing the coin edge-on:

```bash
toolbox pixel frame add coin.pxl.toml spin --blank
toolbox pixel rect coin.pxl.toml k 2,0 5,7 -f 1
toolbox pixel rect coin.pxl.toml y 3,1 4,6 --filled -f 1
toolbox pixel line coin.pxl.toml d 4,2 4,6 -f 1
toolbox pixel set coin.pxl.toml l 3,2 -f 1
toolbox pixel render coin.pxl.toml -o /tmp/coin-preview.png --scale 8   # preview
toolbox pixel render coin.pxl.toml          # export: coin.png (2 frames) + coin.json
```

Frame 1 result:

```
  01234567
0 ..kkkk..
1 ..kyyk..
2 ..kldk..
3 ..kydk..
4 ..kydk..
5 ..kydk..
6 ..kydk..
7 ..kkkk..
```

## 2. Character with idle and walk animations (16x16, drawn with commands)

```bash
F=hero.pxl.toml
toolbox pixel new $F --size 16x16
```

Add the palette to the file:

```toml
[palette]
k = "#1D1D2B outline"
h = "#6B3E26 hair"
s = "#F2C9A0 skin"
b = "#3C6EC8 shirt"
p = "#2B2B44 pants"
```

Block in the body, largest parts first. The sprite is symmetric, so draw details
on the left only and mirror them:

```bash
toolbox pixel rect $F h 5,1 10,3 --filled     # hair
toolbox pixel rect $F s 5,4 10,7 --filled     # face
toolbox pixel set $F k 6,5                    # left eye
toolbox pixel mirror $F --from left           # right eye
toolbox pixel rect $F b 4,8 11,11 --filled    # shirt
toolbox pixel rect $F p 5,12 10,13 --filled   # hips
toolbox pixel rect $F p 5,14 6,14 --filled    # left leg
toolbox pixel mirror $F --from left           # right leg
toolbox pixel outline $F k                    # outline once, at the end
```

```
             111111
   0123456789012345
 0 .....kkkkkk.....
 1 ....khhhhhhk....
 2 ....khhhhhhk....
 3 ....khhhhhhk....
 4 ....kssssssk....
 5 ....kskssksk....
 6 ....kssssssk....
 7 ....kssssssk....
 8 ...kbbbbbbbbk...
 9 ...kbbbbbbbbk...
10 ...kbbbbbbbbk...
11 ...kbbbbbbbbk...
12 ....kppppppk....
13 ....kppppppk....
14 ....kppkkppk....
15 .....kk..kk.....
```

A 4-frame walk: neutral, left leg up, neutral, right leg up. Each frame starts as a
copy, and the last one is the second frame flipped:

```bash
toolbox pixel frame add $F walk --from idle:0     # walk 0: neutral
toolbox pixel frame add $F walk                   # walk 1: copy of walk 0...
toolbox pixel set $F . 5,15 6,15 -a walk -f 1     # ...lift the left foot
toolbox pixel set $F k 5,14 6,14 -a walk -f 1
toolbox pixel frame add $F walk --from walk:0     # walk 2: neutral
toolbox pixel frame add $F walk --from walk:1     # walk 3: copy of walk 1...
toolbox pixel flip $F -a walk -f 3                # ...flipped: right foot up
toolbox pixel render $F -o /tmp/hero-preview.png --scale 8 --layout grid  # preview
toolbox pixel render $F --layout grid          # export: hero.png + hero.json
```

Walk frames 1 and 3, bottom rows:

```
13 ....kppppppk....        13 ....kppppppk....
14 ....kkkkkppk....        14 ....kppkkkkk....
15 .........kk.....        15 .....kk.........
```

`flip` mirrors the whole frame, so it only works like this for a symmetric
front-facing sprite. For side views, change the legs by hand in each frame.

## 3. Starting from an existing image

```bash
toolbox sprite photo.png -s 32 -c 16          # photo_sprite.png: 32 px, 16 colors
toolbox pixel import photo_sprite.png         # photo_sprite.pxl.toml
toolbox pixel show photo_sprite.pxl.toml
```

Imported palettes get keys `a`, `b`, `c`… with the most common color first and no
names. Rename keys and add names in `[palette]` (and update the grid) if you will
edit the sprite a lot, then clean up stray pixels with `set`.
