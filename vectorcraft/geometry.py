from __future__ import annotations

from math import cos, hypot, radians, sin

from .model import Point, Shape


def snap(value: float, grid: int) -> float:
    if grid <= 1:
        return value
    return round(value / grid) * grid


def rotate_point(point: Point, center: Point, angle_deg: float) -> Point:
    angle = radians(angle_deg)
    dx = point.x - center.x
    dy = point.y - center.y
    return Point(center.x + dx * cos(angle) - dy * sin(angle), center.y + dx * sin(angle) + dy * cos(angle))


def transformed_rect_points(shape: Shape) -> list[Point]:
    left, top, right, bottom = shape.bounds()
    points = [Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom)]
    if abs(shape.rotation) < 0.001:
        return points
    center = shape.center()
    return [rotate_point(point, center, shape.rotation) for point in points]


def polygon_bounds(points: list[Point]) -> tuple[float, float, float, float]:
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    j = count - 1
    for i in range(count):
        pi = polygon[i]
        pj = polygon[j]
        crosses = (pi.y > point.y) != (pj.y > point.y)
        if crosses:
            x_intersect = (pj.x - pi.x) * (point.y - pi.y) / ((pj.y - pi.y) or 1e-9) + pi.x
            if point.x < x_intersect:
                inside = not inside
        j = i
    return inside


def distance_point_to_segment(point: Point, start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return hypot(point.x - start.x, point.y - start.y)
    t = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq))
    projection = Point(start.x + t * dx, start.y + t * dy)
    return hypot(point.x - projection.x, point.y - projection.y)


def shape_hit(shape: Shape, point: Point, tolerance: float = 7) -> bool:
    if shape.type == "pen" and shape.points:
        tolerance = max(tolerance, shape.style.width + 4)
        if len(shape.points) == 1:
            return hypot(point.x - shape.points[0].x, point.y - shape.points[0].y) <= tolerance
        return any(
            distance_point_to_segment(point, shape.points[i], shape.points[i + 1]) <= tolerance
            for i in range(len(shape.points) - 1)
        )

    if shape.type in {"line", "arrow", "connector"} and len(shape.points) >= 2:
        return any(
            distance_point_to_segment(point, shape.points[i], shape.points[i + 1]) <= tolerance
            for i in range(len(shape.points) - 1)
        )

    polygon = transformed_rect_points(shape)
    left, top, right, bottom = polygon_bounds(polygon)
    if point.x < left - tolerance or point.x > right + tolerance or point.y < top - tolerance or point.y > bottom + tolerance:
        return False
    if shape.type in {"ellipse", "terminator", "sphere"}:
        center = shape.center()
        rx = max(1, abs(shape.w * shape.scale_x) / 2)
        ry = max(1, abs(shape.h * shape.scale_y) / 2)
        return ((point.x - center.x) ** 2) / (rx * rx) + ((point.y - center.y) ** 2) / (ry * ry) <= 1.15
    return point_in_polygon(point, polygon) or abs(point.x - left) <= tolerance or abs(point.x - right) <= tolerance


def rect_intersects_shape(rect: tuple[float, float, float, float], shape: Shape) -> bool:
    left, top, right, bottom = rect
    s_left, s_top, s_right, s_bottom = shape.bounds()
    return not (s_right < left or s_left > right or s_bottom < top or s_top > bottom)


INSIDE = 0
LEFT = 1
RIGHT = 2
BOTTOM = 4
TOP = 8


def _clip_code(point: Point, rect: tuple[float, float, float, float]) -> int:
    left, top, right, bottom = rect
    code = INSIDE
    if point.x < left:
        code |= LEFT
    elif point.x > right:
        code |= RIGHT
    if point.y < top:
        code |= TOP
    elif point.y > bottom:
        code |= BOTTOM
    return code


def cohen_sutherland_clip(start: Point, end: Point, rect: tuple[float, float, float, float]) -> tuple[Point, Point] | None:
    left, top, right, bottom = rect
    p1 = start.copy()
    p2 = end.copy()
    code1 = _clip_code(p1, rect)
    code2 = _clip_code(p2, rect)

    while True:
        if not (code1 | code2):
            return p1, p2
        if code1 & code2:
            return None

        code_out = code1 or code2
        x = 0.0
        y = 0.0

        if code_out & TOP:
            x = p1.x + (p2.x - p1.x) * (top - p1.y) / ((p2.y - p1.y) or 1e-9)
            y = top
        elif code_out & BOTTOM:
            x = p1.x + (p2.x - p1.x) * (bottom - p1.y) / ((p2.y - p1.y) or 1e-9)
            y = bottom
        elif code_out & RIGHT:
            y = p1.y + (p2.y - p1.y) * (right - p1.x) / ((p2.x - p1.x) or 1e-9)
            x = right
        elif code_out & LEFT:
            y = p1.y + (p2.y - p1.y) * (left - p1.x) / ((p2.x - p1.x) or 1e-9)
            x = left

        if code_out == code1:
            p1 = Point(x, y)
            code1 = _clip_code(p1, rect)
        else:
            p2 = Point(x, y)
            code2 = _clip_code(p2, rect)


def edge_anchor(shape: Shape, toward: Point, gap: float = 8) -> Point:
    left, top, right, bottom = shape.bounds()
    center = shape.center()
    dx = toward.x - center.x
    dy = toward.y - center.y
    if abs(dx) >= abs(dy):
        if dx >= 0:
            return Point(right + gap, center.y)
        return Point(left - gap, center.y)
    if dy >= 0:
        return Point(center.x, bottom + gap)
    return Point(center.x, top - gap)


def connector_points(start_shape: Shape, end_shape: Shape, style: str = "orthogonal") -> list[Point]:
    start_center = start_shape.center()
    end_center = end_shape.center()
    s_left, s_top, s_right, s_bottom = start_shape.bounds()
    e_left, e_top, e_right, e_bottom = end_shape.bounds()
    vertical_gap = 32

    if s_bottom + vertical_gap < e_top:
        start = Point(start_center.x, s_bottom + 8)
        end = Point(end_center.x, e_top - 8)
        vertical_relation = True
    elif e_bottom + vertical_gap < s_top:
        start = Point(start_center.x, s_top - 8)
        end = Point(end_center.x, e_bottom + 8)
        vertical_relation = True
    else:
        start = edge_anchor(start_shape, end_center)
        end = edge_anchor(end_shape, start_center)
        vertical_relation = False

    if style == "straight":
        return [start, end]
    if style == "curve":
        if vertical_relation:
            mid_y = (start.y + end.y) / 2
            return [start, Point(start.x, mid_y), Point(end.x, mid_y), end]
        if abs(start.x - end.x) > abs(start.y - end.y):
            mid_x = (start.x + end.x) / 2
            return [start, Point(mid_x, start.y), Point(mid_x, end.y), end]
        mid_y = (start.y + end.y) / 2
        return [start, Point(start.x, mid_y), Point(end.x, mid_y), end]

    if vertical_relation:
        mid_y = (start.y + end.y) / 2
        return [start, Point(start.x, mid_y), Point(end.x, mid_y), end]
    if abs(start.x - end.x) < 4 or abs(start.y - end.y) < 4:
        return [start, end]
    if abs(start.x - end.x) > abs(start.y - end.y):
        mid_x = (start.x + end.x) / 2
        return [start, Point(mid_x, start.y), Point(mid_x, end.y), end]
    mid_y = (start.y + end.y) / 2
    return [start, Point(start.x, mid_y), Point(end.x, mid_y), end]
