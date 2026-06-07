from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Point, Shape, make_shape


@dataclass
class RecognitionResult:
    shape_type: str
    confidence: float
    detail: str

    @property
    def name(self) -> str:
        mapping = {
            "rect": "矩形",
            "ellipse": "椭圆/圆",
            "triangle": "三角形",
            "diamond": "菱形",
            "line": "直线",
            "arrow": "箭头",
        }
        return mapping.get(self.shape_type, self.shape_type)


def _length(points: list[Point]) -> float:
    total = 0.0
    for i in range(len(points) - 1):
        total += math.hypot(points[i + 1].x - points[i].x, points[i + 1].y - points[i].y)
    return total


def _bounds(points: list[Point]) -> tuple[float, float, float, float]:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _resample(points: list[Point], count: int = 64) -> list[Point]:
    if len(points) < 2:
        return list(points)
    total = _length(points)
    if total < 1e-6:
        return list(points)
    step = total / (count - 1)
    out = [Point(points[0].x, points[0].y)]
    accumulated = 0.0
    i = 1
    prev = points[0]
    while i < len(points):
        current = points[i]
        seg = math.hypot(current.x - prev.x, current.y - prev.y)
        if accumulated + seg >= step:
            ratio = (step - accumulated) / seg if seg > 0 else 0
            nx = prev.x + (current.x - prev.x) * ratio
            ny = prev.y + (current.y - prev.y) * ratio
            new_pt = Point(nx, ny)
            out.append(new_pt)
            prev = new_pt
            accumulated = 0.0
            if len(out) >= count:
                break
        else:
            accumulated += seg
            prev = current
            i += 1
    while len(out) < count:
        out.append(Point(points[-1].x, points[-1].y))
    return out


def _perpendicular_distance(point: Point, start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return math.hypot(point.x - start.x, point.y - start.y)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px = start.x + t * dx
    py = start.y + t * dy
    return math.hypot(point.x - px, point.y - py)


def _douglas_peucker(points: list[Point], tolerance: float) -> list[Point]:
    if len(points) < 3:
        return list(points)
    start, end = points[0], points[-1]
    max_dist = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _perpendicular_distance(points[i], start, end)
        if d > max_dist:
            index = i
            max_dist = d
    if max_dist > tolerance:
        left = _douglas_peucker(points[: index + 1], tolerance)
        right = _douglas_peucker(points[index:], tolerance)
        return left[:-1] + right
    return [start, end]


def _is_closed(points: list[Point], diagonal: float) -> bool:
    if len(points) < 4:
        return False
    gap = math.hypot(points[0].x - points[-1].x, points[0].y - points[-1].y)
    return gap < max(20.0, diagonal * 0.18)


def recognize_stroke(points: list[Point]) -> RecognitionResult | None:
    if len(points) < 4:
        return None

    sampled = _resample(points, 64)
    left, top, right, bottom = _bounds(sampled)
    width = right - left
    height = bottom - top
    diagonal = math.hypot(width, height)
    if diagonal < 18:
        return None

    total_length = _length(sampled)
    straight_distance = math.hypot(sampled[-1].x - sampled[0].x, sampled[-1].y - sampled[0].y)
    closed = _is_closed(sampled, diagonal)

    if not closed and straight_distance / max(1e-6, total_length) > 0.92:
        return RecognitionResult("line", 0.95, "近似直线")

    tolerance = max(6.0, diagonal * 0.06)
    simplified = _douglas_peucker(sampled, tolerance)
    vertex_count = len(simplified) - 1 if closed else len(simplified)

    cx = (left + right) / 2
    cy = (top + bottom) / 2
    rx = max(1.0, width / 2)
    ry = max(1.0, height / 2)
    radii = [
        ((p.x - cx) / rx) ** 2 + ((p.y - cy) / ry) ** 2
        for p in sampled
    ]
    mean_r = sum(radii) / len(radii)
    variance = sum((r - 1.0) ** 2 for r in radii) / len(radii)

    if closed and variance < 0.08 and 0.8 <= mean_r <= 1.25 and vertex_count >= 6:
        return RecognitionResult("ellipse", 0.9, "近似椭圆/圆")

    if closed and 3 <= vertex_count <= 4:
        if vertex_count == 3:
            return RecognitionResult("triangle", 0.85, "三个顶点")
        return _classify_quadrilateral(simplified[:4])

    if closed and vertex_count == 5:
        return _classify_quadrilateral(simplified[:4])

    if not closed and vertex_count == 2:
        return RecognitionResult("line", 0.9, "两端点近似直线")

    return None


def _classify_quadrilateral(vertices: list[Point]) -> RecognitionResult:
    if len(vertices) < 4:
        return RecognitionResult("rect", 0.6, "四边形")
    left = min(p.x for p in vertices)
    right = max(p.x for p in vertices)
    top = min(p.y for p in vertices)
    bottom = max(p.y for p in vertices)
    width = max(1.0, right - left)
    height = max(1.0, bottom - top)
    cx = (left + right) / 2
    cy = (top + bottom) / 2

    rect_score = 0
    diamond_score = 0
    for vertex in vertices:
        on_corner = (
            (abs(vertex.x - left) < width * 0.18 or abs(vertex.x - right) < width * 0.18)
            and (abs(vertex.y - top) < height * 0.18 or abs(vertex.y - bottom) < height * 0.18)
        )
        on_diamond = (
            (abs(vertex.x - cx) < width * 0.18 and (abs(vertex.y - top) < height * 0.18 or abs(vertex.y - bottom) < height * 0.18))
            or (abs(vertex.y - cy) < height * 0.18 and (abs(vertex.x - left) < width * 0.18 or abs(vertex.x - right) < width * 0.18))
        )
        if on_corner:
            rect_score += 1
        if on_diamond:
            diamond_score += 1
    if diamond_score > rect_score:
        return RecognitionResult("diamond", 0.8, "顶点位于中线")
    return RecognitionResult("rect", 0.85, "顶点位于角落")


def shape_from_recognition(stroke: Shape, result: RecognitionResult) -> Shape | None:
    if not stroke.points:
        return None
    left, top, right, bottom = _bounds(stroke.points)
    width = max(20.0, right - left)
    height = max(20.0, bottom - top)
    shape_type = result.shape_type
    if shape_type == "line":
        line = make_shape("line", stroke.points[0].x, stroke.points[0].y, 0, 0)
        line.points = [Point(stroke.points[0].x, stroke.points[0].y), Point(stroke.points[-1].x, stroke.points[-1].y)]
        line.style.stroke = stroke.style.stroke
        line.style.width = max(2, stroke.style.width)
        line.x = min(line.points[0].x, line.points[1].x)
        line.y = min(line.points[0].y, line.points[1].y)
        line.w = abs(line.points[1].x - line.points[0].x)
        line.h = abs(line.points[1].y - line.points[0].y)
        return line

    if shape_type == "ellipse":
        shape = make_shape("ellipse", left, top, width, height)
    elif shape_type == "rect":
        shape = make_shape("rect", left, top, width, height)
    elif shape_type == "triangle":
        shape = make_shape("triangle", left, top, width, height)
    elif shape_type == "diamond":
        shape = make_shape("diamond", left, top, width, height)
    else:
        return None
    shape.style.stroke = stroke.style.stroke
    shape.style.width = max(2, stroke.style.width)
    shape.style.fill = "#ffffff"
    return shape
