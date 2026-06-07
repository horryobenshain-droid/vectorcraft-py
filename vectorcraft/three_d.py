from __future__ import annotations

from .geometry import rotate_point
from .model import Point, Shape


PRISM_TYPES = {"cube", "cuboid"}
THREE_D_TYPES = {"cube", "cuboid", "sphere"}


def bounds_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    a_left, a_top, a_right, a_bottom = a
    b_left, b_top, b_right, b_bottom = b
    return not (a_right < b_left or a_left > b_right or a_bottom < b_top or a_top > b_bottom)


def coord3d_reference(shape: Shape) -> dict[str, Point]:
    left, top, right, bottom = shape.bounds()
    box_w = abs(right - left)
    box_h = abs(bottom - top)
    center = shape.center()
    origin_x = left + box_w * 0.26
    origin_y = bottom - box_h * 0.18
    points = {
        "origin": Point(origin_x, origin_y),
        "x_end": Point(right - box_w * 0.06, origin_y),
        "y_end": Point(left + box_w * 0.62, top + box_h * 0.34),
        "z_end": Point(origin_x, top + box_h * 0.1),
    }
    if abs(shape.rotation) > 0.001:
        return {key: rotate_point(point, center, shape.rotation) for key, point in points.items()}
    return points


def prism_vertices(shape: Shape) -> dict[str, Point]:
    left, top, right, bottom = shape.bounds()
    box_w = abs(right - left)
    box_h = abs(bottom - top)
    depth_ratio = 0.3 if shape.type == "cube" else 0.22
    depth = max(6, min(box_w, box_h) * depth_ratio)
    depth = min(depth, box_w * 0.42, box_h * 0.42)
    points = {
        "ftl": Point(left, top + depth),
        "ftr": Point(right - depth, top + depth),
        "fbr": Point(right - depth, bottom),
        "fbl": Point(left, bottom),
        "btl": Point(left + depth, top),
        "btr": Point(right, top),
        "bbr": Point(right, bottom - depth),
        "bbl": Point(left + depth, bottom - depth),
    }
    if abs(shape.rotation) > 0.001:
        center = shape.center()
        return {key: rotate_point(point, center, shape.rotation) for key, point in points.items()}
    return points


def coord3d_center_limits(coord: Shape) -> tuple[int, int]:
    return getattr(coord, "coord_min", 0), max(getattr(coord, "coord_min", 0) + 1, getattr(coord, "coord_max", 5))


def find_containing_coord(shape: Shape, coords: list[Shape]) -> Shape | None:
    for coord in coords:
        if bounds_intersect(shape.bounds(), coord.bounds()):
            return coord
    return None


def scalar_along(vector: Point, axis: Point) -> float:
    denom = axis.x * axis.x + axis.y * axis.y
    if denom <= 1e-9:
        return 0.0
    return (vector.x * axis.x + vector.y * axis.y) / denom


def format_coord(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 0.08:
        return str(int(rounded))
    return f"{value:.1f}"


def coordinate_tuple_text(values: tuple[float, float, float]) -> str:
    return f"({format_coord(values[0])},{format_coord(values[1])},{format_coord(values[2])})"


def label_position(point: Point, center: Point, distance: float = 14) -> Point:
    dx = point.x - center.x
    dy = point.y - center.y
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-6:
        return Point(point.x, point.y - distance)
    return Point(point.x + dx / length * distance, point.y + dy / length * distance)


def prism_coordinate_labels(prism: Shape, coord: Shape) -> list[tuple[str, Point, tuple[float, float, float]]]:
    vertices = prism_vertices(prism)
    ref = coord3d_reference(coord)
    origin = ref["origin"]
    ux = Point((ref["x_end"].x - origin.x) / 5, (ref["x_end"].y - origin.y) / 5)
    uy = Point((ref["y_end"].x - origin.x) / 5, (ref["y_end"].y - origin.y) / 5)
    uz = Point((ref["z_end"].x - origin.x) / 5, (ref["z_end"].y - origin.y) / 5)

    fbl = vertices["fbl"]
    fbr = vertices["fbr"]
    ftl = vertices["ftl"]
    bbl = vertices["bbl"]
    x0 = scalar_along(Point(fbl.x - origin.x, fbl.y - origin.y), ux)
    z0 = scalar_along(Point(fbl.x - origin.x, fbl.y - origin.y), uz)
    x_len = max(0.2, scalar_along(Point(fbr.x - fbl.x, fbr.y - fbl.y), ux))
    y_len = max(0.2, scalar_along(Point(bbl.x - fbl.x, bbl.y - fbl.y), uy))
    z_len = max(0.2, scalar_along(Point(ftl.x - fbl.x, ftl.y - fbl.y), uz))

    x1 = x0 + x_len
    y0 = 0.0
    y1 = y0 + y_len
    z1 = z0 + z_len
    return [
        ("A", vertices["fbl"], (x0, y0, z0)),
        ("B", vertices["fbr"], (x1, y0, z0)),
        ("C", vertices["ftr"], (x1, y0, z1)),
        ("D", vertices["ftl"], (x0, y0, z1)),
        ("E", vertices["bbl"], (x0, y1, z0)),
        ("F", vertices["bbr"], (x1, y1, z0)),
        ("G", vertices["btr"], (x1, y1, z1)),
        ("H", vertices["btl"], (x0, y1, z1)),
    ]


def sphere_coordinate_labels(sphere: Shape, coord: Shape) -> list[tuple[str, Point, tuple[float, float, float]]]:
    ref = coord3d_reference(coord)
    origin = ref["origin"]
    ux = Point((ref["x_end"].x - origin.x) / 5, (ref["x_end"].y - origin.y) / 5)
    uz = Point((ref["z_end"].x - origin.x) / 5, (ref["z_end"].y - origin.y) / 5)
    center = sphere.center()
    x = scalar_along(Point(center.x - origin.x, center.y - origin.y), ux)
    z = scalar_along(Point(center.x - origin.x, center.y - origin.y), uz)
    return [("C", center, (x, 0.0, z))]
