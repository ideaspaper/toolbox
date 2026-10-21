"""Color helpers: hue-shifted shade ramps, and finding a darker shade of a color.

Pixel artists rarely shade by only darkening: shadows drift toward cool hues
(blue/purple) and highlights toward warm ones (yellow), which keeps the colors lively.
"""

import colorsys

from toolbox.pixel.model import Color, PixelError

COOL_HUE = 240.0  # degrees: where shadows drift
WARM_HUE = 60.0  # where highlights drift
_GRAY = 0.12  # saturation below which a color counts as gray
_SAME_HUE = 40.0  # degrees between two colors of one material


def _hls(color: Color) -> tuple[float, float, float]:
    red, green, blue, _ = color.rgba
    hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    return hue * 360, lightness, saturation


def _hex(hue: float, lightness: float, saturation: float) -> str:
    red, green, blue = colorsys.hls_to_rgb(
        (hue % 360) / 360, min(max(lightness, 0), 1), min(max(saturation, 0), 1)
    )
    return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def _toward(hue: float, target: float, degrees: float) -> float:
    """Turn ``hue`` toward ``target`` the short way, by at most ``degrees``."""
    difference = (target - hue + 180) % 360 - 180
    return hue + max(-degrees, min(degrees, difference))


def ramp(base: Color, steps: int, hue_shift: float = 20.0) -> list[str]:
    """``steps`` shades from darkest to lightest, with ``base`` in the middle.

    The darkest shade turns up to ``hue_shift`` degrees toward blue, the lightest
    toward yellow; shadows get a little more saturated, highlights a little less.
    """
    if not 2 <= steps <= 9:
        raise PixelError("a ramp has 2 to 9 steps")
    hue, lightness, saturation = _hls(base)
    boost = 0.0 if saturation < _GRAY else 0.15  # a gray has no hue to strengthen
    middle = (steps - 1) // 2
    darkest, lightest = lightness * 0.3, lightness + (0.97 - lightness) * 0.75
    shades = []
    for index in range(steps):
        if index < middle:
            t = (middle - index) / middle
            shades.append(
                _hex(
                    _toward(hue, COOL_HUE, hue_shift * t),
                    lightness + (darkest - lightness) * t,
                    saturation + (1 - saturation) * boost * t,
                )
            )
        elif index > middle:
            t = (index - middle) / (steps - 1 - middle)
            shades.append(
                _hex(
                    _toward(hue, WARM_HUE, hue_shift * t),
                    lightness + (lightest - lightness) * t,
                    saturation * (1 - 0.2 * t),
                )
            )
        else:
            shades.append(base.hex[:7])
    return shades


def darker_shade(palette: dict[str, Color], key: str, exclude: set[str]) -> str | None:
    """The darkest palette key of the same material as ``key``, or None.

    Same material means a similar hue (or both gray) and darker than ``key``;
    keys in ``exclude`` and partly transparent colors are skipped.
    """
    hue, lightness, saturation = _hls(palette[key])
    best, best_lightness = None, lightness
    for other, color in palette.items():
        if other == key or other in exclude or color.rgba[3] != 255:
            continue
        other_hue, other_lightness, other_saturation = _hls(color)
        if saturation < _GRAY or other_saturation < _GRAY:
            same = saturation < _GRAY and other_saturation < _GRAY * 2
        else:
            same = abs((other_hue - hue + 180) % 360 - 180) <= _SAME_HUE
        if same and other_lightness < best_lightness:
            best, best_lightness = other, other_lightness
    return best
