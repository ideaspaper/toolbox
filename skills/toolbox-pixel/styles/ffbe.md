# Style guide: detailed side-view battle sprites (FFBE-like)

This is the look of turn-based mobile JRPG battle units such as those in *Final
Fantasy Brave Exvius*: small, chibi-proportioned heroes shown from the side, richly
shaded, with lively looping standby animations and punchy attacks.

**Make original characters in this style. Never copy the game's art.** Do not trace,
import or recreate official sprites, logos, emblems or a named character's exact
costume. Borrowing a general trait the user asks for (a hairstyle, a type of armor, a
color scheme) is fine; the design as a whole must be new.

## Canvas and proportions

| | Value |
|---|---|
| Frame | 64x64 for most units; 80x80 or 96x96 for big weapons, capes or wings |
| Character height | 44-52 px, standing, without weapon or hair spikes |
| Head | 16-20 px wide and tall, about 2.5-3 heads per body |
| Baseline | feet on `y = HEIGHT - 4`, the same row in every frame |
| Anchor | between the feet: `anchor FILE X,Y` |
| Facing | **left**, in a three-quarter view: the face and chest turn slightly toward the viewer |

The party stands on the right of the battle screen and faces enemies on the left. The
side nearest the viewer is the character's left side: the left arm and leg are in
front, the right arm and leg behind (darker, partly hidden). A weapon held in the
right hand therefore crosses in front of the body or sticks out behind it.

**Stance:** feet apart, front (left) foot forward, knees slightly bent, weight low,
weapon ready. Never stand straight and symmetric; the silhouette should lean into the
fight.

## Palette

- **32-48 colors**, at most 62 (the key limit). Build each material as one ramp with
  `ramp`, darkest first. Use an odd number of steps: the base color is the middle
  key, with as many shadows below it as highlights above it:

  | Material | Steps | Example (base on the middle key) |
  |---|---|---|
  | Skin | 5 | `ramp FILE 12345 #F2C4A0 --name skin` (base `3`) |
  | Hair | 5 | `ramp FILE abcde #E8A0B4 --name hair --hue-shift 25` (base `c`) |
  | Metal | 5, plus pure white for glints | `ramp FILE ABCDE #8B9BB4 --name steel` (base `C`) |
  | Main cloth | 5 | `ramp FILE fghij #3B5DC9 --name robe` (base `h`) |
  | Second cloth, leather, gold | 3 each | |
  | Eyes | 2-3 (dark, iris, white glint), by hand | |
  | Outline | 1 very dark, slightly colored, by hand: `k = "#1A1424 outline"` | |
  | Effects | 2-4 bright colors, maybe `#RRGGBBAA` for glows | |

  `ramp` makes 2 to 9 steps, so add single colors (the outline `k`, pure white,
  eye colors) to `[palette]` by hand before drawing with them.

- Light comes from the **top-left, in front of the character**: the face, chest and
  the front arm are lit; the back, the far limbs and under the chin, hair and arms are
  in shadow.
- Hue-shift instead of only darkening; `ramp` does this. Shadows of skin lean red-
  purple, shadows of metal lean blue.
- No dithering. Smooth gradients come from the ramp steps.

## Lines and shading

1. **Outline each part once** on its own layer (`outline FILE k -l LAYER`), then run
   `selout FILE k --inner -l LAYER`. The silhouette keeps the dark line, so the unit reads on
   any background; lines inside the sprite turn into the darker shade of their part.
2. **Shade in three passes:** base color everywhere, then shadow shapes (one or two
   ramp steps darker), then highlights (one or two steps lighter) on the lit planes.
3. **Hand-place in-between pixels** on curve steps inside the sprite, such as a
   shoulder or the hair's edge against the face. Do not add them on the outside edge
   against transparency: they look like a halo in game.
4. **Highlights tell the material:** a soft band across hair, hard white glints on
   metal and eyes, broad light planes on cloth, no glint on leather.
5. **Faces:** eyes 2-3 px tall with a 1-pixel glint, a 1-pixel mouth, the far eye
   narrower than the near one. At this size the face carries the character.

## Layers

Plan layers so each moving part is separate:

| Layer | Holds |
|---|---|
| `back` | the cape, back hair, far arm and far leg |
| `body` | torso, near leg, head and face |
| `hair` | the front hair and bangs (they lag behind motion) |
| `front` | the near arm and the weapon |
| `fx` | magic glows, slashes, sparkles |

`new FILE --size 64x64 --animation standby --layers back,body,hair,front,fx`

## Animation set

| Animation | Frames | Timing | Notes |
|---|---|---|---|
| `standby` | 4-8, loop | 100-150 ms | breathing: `move` the upper body down 1 px and back; hair and cape follow one frame later; the weapon bobs 1 px |
| `attack` | 6-10 | anticipation held 150-250 ms, smear 40-60 ms, impact held 150 ms | wind up backward, a smear or slash on `fx`, then recover to standby |
| `magic_standby` | 2-4, loop | 120 ms | weapon or hand raised, a pulsing glow on `fx` |
| `cast` | 4-6 | | the release: a burst on `fx`, the body leans forward |
| `limit` | 8-12 | | the special move: the biggest pose, hold the climax |
| `hurt` | 1-2 | 150 ms | lean back 2-3 px, eyes shut |
| `dying` / `dead` | 2-3 / 1 | | kneel, then lie or slump |
| `victory` | 4-8 | | a weapon flourish or a confident pose |
| `move` | 4-6, loop | 80-100 ms | a run cycle toward the left |

Keep the feet on the baseline in every frame except jumps and knockbacks. A 1-pixel
change reads clearly; move secondary parts (hair, cape, sleeves) one frame after the
body to give follow-through.

## Workflow

Work in stages and render a preview after each one
(`render FILE -a A -f N --scale 6 -o /tmp/p.png`); fix problems before moving on.
`render` always stacks every layer (its `-l` is `--layout`); to inspect one layer
use `show FILE -a A -f N -l LAYER`.

1. **Blocking.** On `body`, draw the pose with flat filled shapes in one mid color per
   part (head circle, torso, limbs, weapon): `ellipse --filled` for the head and
   round parts, `polygon --filled` for the torso, limbs and blade. Check the
   silhouette and proportions.
2. **Base colors.** Recolor each part with its ramp's middle color.
3. **Outline**, per layer, then `selout --inner`.
4. **Shadows, then highlights, then details** (face, trims, buckles, hair strands).
5. **Animate standby** from the finished frame: `frame add` copies, `move` the upper
   body, `copy --from` reuses parts, `rotate` the weapon on `front`.
   Check each new frame with `render -f N --onion` and the loop with `render --gif`.
6. **Time it** with `frame duration`, set the `anchor`, and export at scale 1.

At 64x64, writing whole grids by hand is error-prone. Write rows with a short script
that builds and checks them, or draw with commands, and print the frame after each
step.
