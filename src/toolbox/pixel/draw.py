"""Drawing operations on one frame. Each returns a new grid; inputs are not changed.

Coordinates are 0-based ``(x, y)`` from the top-left. Keys are palette characters or
``.`` (transparent); callers check keys against the palette.
"""

import math
from collections import Counter
from enum import StrEnum

from toolbox.pixel.color import darker_shade
from toolbox.pixel.model import TRANSPARENT, Color, Grid, PixelError


class Side(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class Direction(StrEnum):
    HORIZONTAL = "horizontal"  # swap left and right, e.g. to face the other way
    VERTICAL = "vertical"  # swap top and bottom


def _copy(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def _check_point(grid: Grid, x: int, y: int) -> None:
    width, height = len(grid[0]), len(grid)
    if not (0 <= x < width and 0 <= y < height):
        raise PixelError(
            f"point {x},{y} is outside the {width}x{height} frame "
            f"(x 0-{width - 1}, y 0-{height - 1})"
        )


def set_pixels(grid: Grid, points: list[tuple[int, int]], key: str) -> Grid:
    for x, y in points:
        _check_point(grid, x, y)
    result = _copy(grid)
    for x, y in points:
        result[y][x] = key
    return result


def _line_points(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """The pixels of a 1-pixel line from ``start`` to ``end`` (Bresenham)."""
    (x, y), (x1, y1) = start, end
    dx, dy = abs(x1 - x), -abs(y1 - y)
    step_x, step_y = (1 if x < x1 else -1), (1 if y < y1 else -1)
    error = dx + dy
    points = []
    while True:
        points.append((x, y))
        if (x, y) == (x1, y1):
            break
        double = 2 * error
        if double >= dy:
            error += dy
            x += step_x
        if double <= dx:
            error += dx
            y += step_y
    return points


def line(grid: Grid, start: tuple[int, int], end: tuple[int, int], key: str) -> Grid:
    """A 1-pixel line from ``start`` to ``end``, both included."""
    _check_point(grid, *start)
    _check_point(grid, *end)
    return set_pixels(grid, _line_points(start, end), key)


def rect(
    grid: Grid,
    corner: tuple[int, int],
    opposite: tuple[int, int],
    key: str,
    filled: bool = False,
) -> Grid:
    """A rectangle between two corners, both included; only the border unless filled."""
    _check_point(grid, *corner)
    _check_point(grid, *opposite)
    left, right = sorted((corner[0], opposite[0]))
    top, bottom = sorted((corner[1], opposite[1]))
    points = [
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if filled or x in (left, right) or y in (top, bottom)
    ]
    return set_pixels(grid, points, key)


def ellipse(
    grid: Grid,
    corner: tuple[int, int],
    opposite: tuple[int, int],
    key: str,
    filled: bool = False,
) -> Grid:
    """An ellipse (or circle) that fits the box between two corners, both included.

    Pixels whose centers fall inside the ellipse form the shape, and the outline is
    the ones next to a pixel outside it, so it is one pixel thick without gaps. The
    middle row and column always reach the box's edges, even on very thin boxes.
    """
    left, top, right, bottom = _region(grid, corner, opposite)
    center_x, center_y = (left + right) / 2, (top + bottom) / 2
    radius_x, radius_y = (right - left + 1) / 2, (bottom - top + 1) / 2
    inside = {
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2 <= 1
        or y in (math.floor(center_y), math.ceil(center_y))
        or x in (math.floor(center_x), math.ceil(center_x))
    }
    points = [
        (x, y)
        for x, y in inside
        if filled
        or any(
            (x + nx, y + ny) not in inside
            for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    ]
    return set_pixels(grid, points, key)


def polygon(
    grid: Grid, corners: list[tuple[int, int]], key: str, filled: bool = False
) -> Grid:
    """A closed shape through ``corners`` in order; only the border unless filled.

    Filled, it also covers the pixels inside the border (even-odd rule, so a shape
    whose sides cross leaves the overlap empty).
    """
    if len(corners) < 3:
        raise PixelError(f"a polygon needs at least 3 corners, got {len(corners)}")
    for point in corners:
        _check_point(grid, *point)
    points = []
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        points += _line_points(start, end)
    if filled:
        xs, ys = [x for x, _ in corners], [y for _, y in corners]
        points += [
            (x, y)
            for y in range(min(ys), max(ys) + 1)
            for x in range(min(xs), max(xs) + 1)
            if _inside_polygon(x, y, corners)
        ]
    return set_pixels(grid, points, key)


def _inside_polygon(x: int, y: int, corners: list[tuple[int, int]]) -> bool:
    """Even-odd test: does a ray from ``x, y`` to the right cross an odd number
    of sides?"""
    inside = False
    for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1], strict=True):
        if (y0 > y) != (y1 > y) and x < x0 + (x1 - x0) * (y - y0) / (y1 - y0):
            inside = not inside
    return inside


def fill(grid: Grid, start: tuple[int, int], key: str) -> Grid:
    """Flood-fill the area of same-colored pixels around ``start`` (4-connected)."""
    _check_point(grid, *start)
    result = _copy(grid)
    target = result[start[1]][start[0]]
    if target == key:
        return result
    width, height = len(result[0]), len(result)
    pending = [start]
    while pending:
        x, y = pending.pop()
        if 0 <= x < width and 0 <= y < height and result[y][x] == target:
            result[y][x] = key
            pending += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return result


def mirror(grid: Grid, source: Side) -> Grid:
    """Copy one half onto the other, mirrored, making the frame symmetric."""
    result = _copy(grid)
    width, height = len(result[0]), len(result)
    if source in (Side.LEFT, Side.RIGHT):
        for row in result:
            for x in range(width // 2):
                if source is Side.LEFT:
                    row[width - 1 - x] = row[x]
                else:
                    row[x] = row[width - 1 - x]
    else:
        for y in range(height // 2):
            if source is Side.TOP:
                result[height - 1 - y] = result[y][:]
            else:
                result[y] = result[height - 1 - y][:]
    return result


def flip(grid: Grid, direction: Direction) -> Grid:
    if direction is Direction.HORIZONTAL:
        return [row[::-1] for row in grid]
    return [row[:] for row in grid[::-1]]


def shift(grid: Grid, dx: int, dy: int, wrap: bool = False) -> Grid:
    """Move every pixel by ``dx, dy``; uncovered pixels become transparent."""
    width, height = len(grid[0]), len(grid)
    result = [[TRANSPARENT] * width for _ in range(height)]
    for y, row in enumerate(grid):
        for x, key in enumerate(row):
            new_x, new_y = x + dx, y + dy
            if wrap:
                new_x, new_y = new_x % width, new_y % height
            if 0 <= new_x < width and 0 <= new_y < height:
                result[new_y][new_x] = key
    return result


def outline(grid: Grid, key: str, diagonal: bool = False) -> Grid:
    """Color transparent pixels that touch the shape, drawing an outline around it."""
    width, height = len(grid[0]), len(grid)
    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diagonal:
        neighbors += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    result = _copy(grid)
    for y in range(height):
        for x in range(width):
            if grid[y][x] != TRANSPARENT:
                continue
            if any(
                0 <= x + nx < width
                and 0 <= y + ny < height
                and grid[y + ny][x + nx] != TRANSPARENT
                for nx, ny in neighbors
            ):
                result[y][x] = key
    return result


def recolor(grid: Grid, old: str, new: str) -> Grid:
    return [[new if key == old else key for key in row] for row in grid]


def _region(
    grid: Grid, corner: tuple[int, int], opposite: tuple[int, int]
) -> tuple[int, int, int, int]:
    """``left, top, right, bottom`` of the rectangle between two corners."""
    _check_point(grid, *corner)
    _check_point(grid, *opposite)
    left, right = sorted((corner[0], opposite[0]))
    top, bottom = sorted((corner[1], opposite[1]))
    return left, top, right, bottom


def copy_region(
    source: Grid,
    corner: tuple[int, int],
    opposite: tuple[int, int],
    target: Grid,
    to: tuple[int, int],
) -> Grid:
    """Paste a rectangle of ``source`` onto ``target`` with its top-left at ``to``.

    Transparent source pixels leave the target as it is (like a stamp), and pixels
    that land outside the frame are dropped.
    """
    left, top, right, bottom = _region(source, corner, opposite)
    _check_point(target, *to)
    result = _copy(target)
    width, height = len(result[0]), len(result)
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            key = source[y][x]
            new_x, new_y = to[0] + x - left, to[1] + y - top
            if key != TRANSPARENT and 0 <= new_x < width and 0 <= new_y < height:
                result[new_y][new_x] = key
    return result


def move_region(
    grid: Grid,
    corner: tuple[int, int],
    opposite: tuple[int, int],
    dx: int,
    dy: int,
) -> Grid:
    """Move a rectangle by ``dx, dy``; the area it leaves becomes transparent."""
    left, top, right, bottom = _region(grid, corner, opposite)
    cleared = _copy(grid)
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            cleared[y][x] = TRANSPARENT
    width, height = len(grid[0]), len(grid)
    result = cleared
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            key = grid[y][x]
            new_x, new_y = x + dx, y + dy
            if key != TRANSPARENT and 0 <= new_x < width and 0 <= new_y < height:
                result[new_y][new_x] = key
    return result


def _scale2x(grid: Grid) -> Grid:
    """Double the size with EPX, which rounds diagonal steps instead of blocking."""
    width, height = len(grid[0]), len(grid)
    result = [[TRANSPARENT] * (width * 2) for _ in range(height * 2)]
    for y in range(height):
        for x in range(width):
            p = grid[y][x]
            a = grid[y - 1][x] if y > 0 else p
            b = grid[y][x + 1] if x < width - 1 else p
            c = grid[y][x - 1] if x > 0 else p
            d = grid[y + 1][x] if y < height - 1 else p
            result[2 * y][2 * x] = a if c == a and c != d and a != b else p
            result[2 * y][2 * x + 1] = b if a == b and a != c and b != d else p
            result[2 * y + 1][2 * x] = c if d == c and d != b and c != a else p
            result[2 * y + 1][2 * x + 1] = d if b == d and b != a and d != c else p
    return result


def rotate(
    grid: Grid, degrees: float, pivot: tuple[float, float] | None = None
) -> Grid:
    """Rotate clockwise around ``pivot`` (default: the frame's center).

    Multiples of 90 degrees are exact. Other angles use RotSprite's idea: enlarge 8
    times with EPX, rotate, and sample each pixel's center, which keeps lines clean.
    """
    width, height = len(grid[0]), len(grid)
    if pivot is None:
        center_x, center_y = width / 2, height / 2
    else:
        _check_point(grid, int(pivot[0]), int(pivot[1]))
        center_x, center_y = pivot[0] + 0.5, pivot[1] + 0.5  # the pixel's center
    exact = degrees % 90 == 0
    factor = 1 if exact else 8
    source = grid
    for _ in range(0 if exact else 3):
        source = _scale2x(source)
    radians = math.radians(degrees)
    cos, sin = math.cos(radians), math.sin(radians)
    if exact:  # avoid 6e-17 instead of 0 pushing samples into the wrong pixel
        cos, sin = round(cos), round(sin)
    result = [[TRANSPARENT] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            # Turn this pixel's center back by the angle to find where it came from.
            rx, ry = x + 0.5 - center_x, y + 0.5 - center_y
            source_x = center_x + rx * cos + ry * sin
            source_y = center_y - rx * sin + ry * cos
            sx, sy = math.floor(source_x * factor), math.floor(source_y * factor)
            if 0 <= sx < width * factor and 0 <= sy < height * factor:
                result[y][x] = source[sy][sx]
    return result


def selout(
    grid: Grid,
    palette: dict[str, Color],
    key: str,
    inner: bool = False,
) -> Grid:
    """Recolor ``key`` outline pixels with a darker shade of the color they border.

    This is selective outlining: each part gets an outline of its own hue instead of
    one dark line everywhere. With ``inner``, pixels that touch transparency keep
    ``key``, so the silhouette stays crisp and only the lines inside change.
    """
    width, height = len(grid[0]), len(grid)
    shades: dict[str, str | None] = {}
    result = _copy(grid)
    for y in range(height):
        for x in range(width):
            if grid[y][x] != key:
                continue
            neighbors = [
                grid[y + ny][x + nx]
                if 0 <= x + nx < width and 0 <= y + ny < height
                else TRANSPARENT
                for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ]
            if inner and TRANSPARENT in neighbors:
                continue
            materials = Counter(n for n in neighbors if n not in (key, TRANSPARENT))
            if not materials:
                continue
            # Ties go to the darker material, which reads as the shadow side.
            material = min(
                materials,
                key=lambda k: (-materials[k], sum(palette[k].rgba[:3])),
            )
            if material not in shades:
                shades[material] = darker_shade(palette, material, {key})
            if shades[material] is not None:
                result[y][x] = shades[material]
    return result
