from __future__ import annotations

from base64 import b64decode
import json
from pathlib import Path
from xml.sax.saxutils import escape

from .geometry import connector_points, rotate_point
from .model import Document, Point, Shape
from .renderer import Renderer
from .three_d import coord3d_reference, coordinate_tuple_text, find_containing_coord, label_position, prism_coordinate_labels, sphere_coordinate_labels


def save_json(document: Document, path: str | Path) -> None:
    Path(path).write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: str | Path) -> Document:
    return Document.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_workspace(pages: list[tuple[str, Document]], path: str | Path) -> None:
    data = {
        "app": "VectorCraft-Py",
        "version": "1.1",
        "kind": "workspace",
        "pages": [{"name": name, "document": doc.to_dict()} for name, doc in pages],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_workspace(path: str | Path) -> list[tuple[str, Document]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and raw.get("kind") == "workspace" and isinstance(raw.get("pages"), list):
        return [(page.get("name") or f"页面 {index + 1}", Document.from_dict(page["document"])) for index, page in enumerate(raw["pages"])]
    return [("页面 1", Document.from_dict(raw))]


def export_png(document: Document, path: str | Path) -> None:
    Renderer().render_document(document).save(path)


def export_svg(document: Document, path: str | Path) -> None:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{document.width}" height="{document.height}" viewBox="0 0 {document.width} {document.height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#1f2a44"/></marker></defs>',
        f'<rect x="0" y="0" width="{document.width}" height="{document.height}" fill="{document.background}"/>',
    ]
    for shape in document.shapes:
        if shape.type == "coord3d":
            parts.append(coord3d_svg(shape, "background"))
    for shape in document.shapes:
        if shape.type != "coord3d":
            parts.append(shape_to_svg(document, shape))
    for shape in document.shapes:
        if shape.type == "coord3d":
            parts.append(coord3d_svg(shape, "foreground"))
    parts.extend(coordinate_annotations_svg(document))
    parts.append("</svg>")
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def style_attrs(shape: Shape) -> str:
    style = shape.style
    dash = ""
    if style.dash == "dashed":
        dash = ' stroke-dasharray="10 7"'
    elif style.dash == "dotted":
        dash = ' stroke-dasharray="2 6"'
    return (
        f'fill="{style.fill}" stroke="{style.stroke}" stroke-width="{style.width}" '
        f'opacity="{style.opacity}"{dash}'
    )


def shape_to_svg(document: Document, shape: Shape) -> str:
    if shape.type == "connector" and shape.connection:
        start = document.shape_by_id(shape.connection.start_id)
        end = document.shape_by_id(shape.connection.end_id)
        if start and end:
            shape = Shape.from_dict(shape.to_dict())
            shape.points = connector_points(start, end, shape.connection.style)
    left, top, right, bottom = shape.bounds()
    w = right - left
    h = bottom - top
    transform = ""
    if abs(shape.rotation) > 0.001:
        cx = left + w / 2
        cy = top + h / 2
        transform = f' transform="rotate({shape.rotation} {cx} {cy})"'

    if shape.type in {"line", "arrow", "connector"} and len(shape.points) >= 2:
        points = " ".join(f"{p.x},{p.y}" for p in shape.points)
        marker = ""
        if shape.type in {"arrow", "connector"}:
            marker = ' marker-end="url(#arrow)"'
        return f'<polyline points="{points}" fill="none" {style_attrs(shape)}{marker}/>'
    if shape.type == "image":
        if not shape.image_data:
            return f'<rect x="{left}" y="{top}" width="{w}" height="{h}" fill="#f7f9fc" stroke="#8b97a8" stroke-dasharray="8 6"{transform}/>'
        mime = shape.image_mime or _guess_image_mime(shape.image_data)
        href = f"data:{mime};base64,{shape.image_data}"
        outline = ""
        if shape.style.width > 0:
            outline = f'<rect x="{left}" y="{top}" width="{w}" height="{h}" fill="none" stroke="{shape.style.stroke}" stroke-width="{shape.style.width}" opacity="{shape.style.opacity}"{transform}/>'
        return f'<image x="{left}" y="{top}" width="{w}" height="{h}" href="{href}" preserveAspectRatio="none"{transform}/>{outline}'
    if shape.type == "pen":
        if len(shape.points) >= 2:
            points = " ".join(f"{p.x},{p.y}" for p in shape.points)
            return (
                f'<polyline points="{points}" fill="none" stroke="{shape.style.stroke}" '
                f'stroke-width="{shape.style.width}" opacity="{shape.style.opacity}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        if shape.points:
            point = shape.points[0]
            radius = max(2, shape.style.width)
            return f'<circle cx="{point.x}" cy="{point.y}" r="{radius}" fill="{shape.style.stroke}" opacity="{shape.style.opacity}"/>'
        return ""
    if shape.type in {"ellipse", "terminator"}:
        return f'<ellipse cx="{left + w / 2}" cy="{top + h / 2}" rx="{w / 2}" ry="{h / 2}" {style_attrs(shape)}{transform}/>{text_svg(shape)}'
    if shape.type in {"diamond", "decision"}:
        points = f"{left + w / 2},{top} {right},{top + h / 2} {left + w / 2},{bottom} {left},{top + h / 2}"
        return f'<polygon points="{points}" {style_attrs(shape)}{transform}/>{text_svg(shape)}'
    if shape.type == "triangle":
        points = f"{left + w / 2},{top} {right},{bottom} {left},{bottom}"
        return f'<polygon points="{points}" {style_attrs(shape)}{transform}/>{text_svg(shape)}'
    if shape.type in {"cube", "cuboid"}:
        return prism_svg(shape)
    if shape.type == "sphere":
        guide = shape.style.stroke
        return (
            f'<ellipse cx="{left + w / 2}" cy="{top + h / 2}" rx="{w / 2}" ry="{h / 2}" {style_attrs(shape)}{transform}/>'
            f'<ellipse cx="{left + w / 2}" cy="{top + h / 2}" rx="{w * 0.21}" ry="{h / 2}" fill="none" stroke="{guide}" stroke-width="{max(1, shape.style.width * 0.6)}" opacity="{shape.style.opacity * 0.45}"{transform}/>'
            f'<ellipse cx="{left + w / 2}" cy="{top + h / 2}" rx="{w / 2}" ry="{h * 0.17}" fill="none" stroke="{guide}" stroke-width="{max(1, shape.style.width * 0.6)}" opacity="{shape.style.opacity * 0.45}"{transform}/>'
            f'<ellipse cx="{left + w / 2}" cy="{top + h / 2}" rx="{w * 0.37}" ry="{h * 0.37}" fill="none" stroke="{guide}" stroke-width="{max(1, shape.style.width * 0.6)}" opacity="{shape.style.opacity * 0.45}"{transform}/>'
            f'<ellipse cx="{left + w * 0.33}" cy="{top + h * 0.33}" rx="{w * 0.09}" ry="{h * 0.06}" fill="#ffffff" stroke="none" opacity="0.36"{transform}/>'
            f'{text_svg(shape)}'
        )
    if shape.type == "coord3d":
        return coord3d_svg(shape, "foreground")
    return f'<rect x="{left}" y="{top}" width="{w}" height="{h}" rx="{min(w, h) * 0.15 if shape.type in {"round_rect", "org_node"} else 0}" {style_attrs(shape)}{transform}/>{text_svg(shape)}'


def svg_points(points: list[Point]) -> str:
    return " ".join(f"{point.x},{point.y}" for point in points)


def shifted_color(color: str, amount: int) -> str:
    raw = color.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(part * 2 for part in raw)
    try:
        channels = [int(raw[i : i + 2], 16) for i in range(0, 6, 2)]
    except Exception:
        channels = [238, 248, 250]
    if amount >= 0:
        channels = [min(255, channel + amount) for channel in channels]
    else:
        channels = [max(0, channel + amount) for channel in channels]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def prism_svg(shape: Shape) -> str:
    left, top, right, bottom = shape.bounds()
    w = right - left
    h = bottom - top
    depth_ratio = 0.3 if shape.type == "cube" else 0.22
    depth = max(6, min(w, h) * depth_ratio)
    depth = min(depth, w * 0.42, h * 0.42)
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
        points = {key: rotate_point(point, center, shape.rotation) for key, point in points.items()}
    top_face = [points["ftl"], points["ftr"], points["btr"], points["btl"]]
    side_face = [points["ftr"], points["fbr"], points["bbr"], points["btr"]]
    front_face = [points["ftl"], points["ftr"], points["fbr"], points["fbl"]]
    style = shape.style
    base = f'stroke="{style.stroke}" stroke-width="{style.width}" opacity="{style.opacity}"'
    hidden = f'stroke="{style.stroke}" stroke-width="{max(1, style.width - 1)}" opacity="{style.opacity * 0.38}" stroke-dasharray="8 6" fill="none"'
    hidden_lines = [
        f'<line x1="{points["btl"].x}" y1="{points["btl"].y}" x2="{points["bbl"].x}" y2="{points["bbl"].y}" {hidden}/>',
        f'<line x1="{points["bbl"].x}" y1="{points["bbl"].y}" x2="{points["bbr"].x}" y2="{points["bbr"].y}" {hidden}/>',
        f'<line x1="{points["bbl"].x}" y1="{points["bbl"].y}" x2="{points["fbl"].x}" y2="{points["fbl"].y}" {hidden}/>',
    ]
    return (
        f'<polygon points="{svg_points(top_face)}" fill="{shifted_color(style.fill, 18)}" {base}/>'
        f'<polygon points="{svg_points(side_face)}" fill="{shifted_color(style.fill, -12)}" {base}/>'
        f'<polygon points="{svg_points(front_face)}" fill="{style.fill}" {base}/>'
        + "".join(hidden_lines)
        + text_svg(shape)
    )


def coord3d_svg(shape: Shape, layer: str = "foreground") -> str:
    def place(point: Point) -> Point:
        return point

    ref = coord3d_reference(shape)
    origin = ref["origin"]
    x_end = ref["x_end"]
    y_end = ref["y_end"]
    z_end = ref["z_end"]
    color = shape.style.stroke
    width = max(2, shape.style.width)
    guide = f'stroke="{color}" stroke-width="1" opacity="{shape.style.opacity * 0.22}" stroke-dasharray="2 6" fill="none"'
    axis = f'stroke="{color}" stroke-width="{width}" opacity="{shape.style.opacity}" fill="none" marker-end="url(#arrow)"'
    x_vec = Point(x_end.x - origin.x, x_end.y - origin.y)
    y_vec = Point(y_end.x - origin.x, y_end.y - origin.y)
    parts: list[str] = []
    coord_min = getattr(shape, "coord_min", 0)
    coord_max = max(coord_min + 1, getattr(shape, "coord_max", 5))
    ticks = max(1, coord_max - coord_min)
    if layer == "background":
        for i in range(1, ticks):
            t = i / ticks
            p_x = Point(origin.x + x_vec.x * t, origin.y + x_vec.y * t)
            p_y = Point(origin.x + y_vec.x * t, origin.y + y_vec.y * t)
            grid_x_end = Point(p_x.x + y_vec.x * 0.58, p_x.y + y_vec.y * 0.58)
            grid_y_end = Point(p_y.x + x_vec.x * 0.58, p_y.y + x_vec.y * 0.58)
            p_x = place(p_x)
            p_y = place(p_y)
            grid_x_end = place(grid_x_end)
            grid_y_end = place(grid_y_end)
            parts.append(f'<line x1="{p_x.x}" y1="{p_x.y}" x2="{grid_x_end.x}" y2="{grid_x_end.y}" {guide}/>')
            parts.append(f'<line x1="{p_y.x}" y1="{p_y.y}" x2="{grid_y_end.x}" y2="{grid_y_end.y}" {guide}/>')
        z_vec = Point(z_end.x - origin.x, z_end.y - origin.y)
        yz_guide = f'stroke="{color}" stroke-width="1" opacity="{shape.style.opacity * 0.18}" stroke-dasharray="2 6" fill="none"'
        for i in range(1, ticks):
            t = i / ticks
            p_z = Point(origin.x + z_vec.x * t, origin.y + z_vec.y * t)
            grid_z_end = Point(p_z.x + y_vec.x * 0.42, p_z.y + y_vec.y * 0.42)
            p_z = place(p_z)
            grid_z_end = place(grid_z_end)
            parts.append(f'<line x1="{p_z.x}" y1="{p_z.y}" x2="{grid_z_end.x}" y2="{grid_z_end.y}" {yz_guide}/>')
        return "".join(parts)

    for i in range(1, ticks):
        t = i / ticks
        p_x = Point(origin.x + x_vec.x * t, origin.y + x_vec.y * t)
        p_y = Point(origin.x + y_vec.x * t, origin.y + y_vec.y * t)
        pz = Point(origin.x + (z_end.x - origin.x) * t, origin.y + (z_end.y - origin.y) * t)
        label_value = coord_min + i
        p_x_label = place(Point(p_x.x, p_x.y + 8))
        p_y_label = place(Point(p_y.x - 8, p_y.y))
        p_z_label = place(Point(pz.x - 8, pz.y))
        parts.append(f'<text x="{p_x_label.x}" y="{p_x_label.y}" text-anchor="middle" dominant-baseline="middle" font-size="10" fill="{color}">{label_value}</text>')
        parts.append(f'<text x="{p_y_label.x}" y="{p_y_label.y}" text-anchor="middle" dominant-baseline="middle" font-size="10" fill="{color}">{label_value}</text>')
        parts.append(f'<text x="{p_z_label.x}" y="{p_z_label.y}" text-anchor="middle" dominant-baseline="middle" font-size="10" fill="{color}">{label_value}</text>')
    for end in [x_end, y_end, z_end]:
        start = place(origin)
        placed_end = place(end)
        parts.append(f'<line x1="{start.x}" y1="{start.y}" x2="{placed_end.x}" y2="{placed_end.y}" {axis}/>')
        parts.extend(axis_ticks_svg(origin, end, shape))
    labels = [
        ("x", Point(x_end.x + 10, x_end.y + 2), 14),
        ("y", Point(y_end.x + 10, y_end.y - 8), 14),
        ("z", Point(z_end.x, z_end.y - 14), 14),
        ("O", Point(origin.x - 12, origin.y + 14), 13),
    ]
    for label, point, size in labels:
        point = place(point)
        parts.append(f'<text x="{point.x}" y="{point.y}" text-anchor="middle" dominant-baseline="middle" font-size="{size}" fill="{color}">{label}</text>')
    return "".join(parts) + text_svg(shape)


def axis_ticks_svg(start: Point, end: Point, shape: Shape) -> list[str]:
    dx = end.x - start.x
    dy = end.y - start.y
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    nx = -dy / length * 4
    ny = dx / length * 4
    center = shape.center()
    parts: list[str] = []
    for i in range(1, 5):
        t = i / 5
        point = Point(start.x + dx * t, start.y + dy * t)
        p1 = Point(point.x - nx, point.y - ny)
        p2 = Point(point.x + nx, point.y + ny)
        if abs(shape.rotation) > 0.001:
            p1 = rotate_point(p1, center, shape.rotation)
            p2 = rotate_point(p2, center, shape.rotation)
        parts.append(f'<line x1="{p1.x}" y1="{p1.y}" x2="{p2.x}" y2="{p2.y}" stroke="{shape.style.stroke}" stroke-width="1" opacity="{shape.style.opacity * 0.68}"/>')
    return parts


def coordinate_annotations_svg(document: Document) -> list[str]:
    coords = [shape for shape in document.shapes if shape.type == "coord3d"]
    if not coords:
        return []
    parts: list[str] = []
    for shape in document.shapes:
        if shape.type not in {"cube", "cuboid", "sphere"}:
            continue
        coord = find_containing_coord(shape, coords)
        if not coord:
            continue
        labels = prism_coordinate_labels(shape, coord) if shape.type in {"cube", "cuboid"} else sphere_coordinate_labels(shape, coord)
        center = shape.center()
        for name, point, values in labels:
            pos = label_position(point, center, 14)
            text = f"{name}{coordinate_tuple_text(values)}"
            parts.append(coordinate_label_svg(pos, text))
    return parts


def coordinate_label_svg(point: Point, text: str) -> str:
    width = max(24, len(text) * 7)
    height = 16
    left = point.x - width / 2
    top = point.y - height / 2
    return (
        f'<g class="coord-label">'
        f'<rect x="{left}" y="{top}" width="{width}" height="{height}" rx="3" fill="#ffffff" opacity="0.86" stroke="#b8c2d0" stroke-width="1"/>'
        f'<text x="{point.x}" y="{point.y + 1}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="11" fill="#1f2a44">{escape(text)}</text>'
        f'</g>'
    )


def text_svg(shape: Shape) -> str:
    if not shape.text:
        return ""
    center = shape.center()
    return (
        f'<text x="{center.x}" y="{center.y}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="{shape.style.font_size}" fill="{shape.style.stroke}">{escape(shape.text)}</text>'
    )


def _guess_image_mime(data: str) -> str:
    try:
        raw = b64decode(data[:48] + "===")
    except Exception:
        return "image/png"
    if raw.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG"):
        return "image/png"
    if raw.startswith(b"GIF"):
        return "image/gif"
    return "image/png"
