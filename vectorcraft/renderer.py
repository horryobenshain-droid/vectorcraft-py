from __future__ import annotations

from base64 import b64decode
from dataclasses import replace
from io import BytesIO
from math import atan2, cos, pi, sin

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from .geometry import connector_points, rotate_point, transformed_rect_points
from .model import Document, Point, Shape, Style
from .three_d import coord3d_reference, coordinate_tuple_text, find_containing_coord, label_position, prism_coordinate_labels, sphere_coordinate_labels


def hex_to_rgba(color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    color = color.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(part * 2 for part in color)
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
    except Exception:
        r, g, b = 0, 0, 0
    return r, g, b, int(max(0.0, min(1.0, opacity)) * 255)


def blend(dst: tuple[int, int, int, int], src: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    alpha = src[3] / 255
    inv = 1 - alpha
    return (
        int(src[0] * alpha + dst[0] * inv),
        int(src[1] * alpha + dst[1] * inv),
        int(src[2] * alpha + dst[2] * inv),
        255,
    )


def flatten_rgba(color: tuple[int, int, int, int], base: tuple[int, int, int] = (255, 255, 255)) -> tuple[int, int, int, int]:
    alpha = color[3] / 255
    inv = 1 - alpha
    return (
        int(color[0] * alpha + base[0] * inv),
        int(color[1] * alpha + base[1] * inv),
        int(color[2] * alpha + base[2] * inv),
        255,
    )


def tint_rgba(color: tuple[int, int, int, int], target: tuple[int, int, int], amount: float) -> tuple[int, int, int, int]:
    amount = max(0.0, min(1.0, amount))
    inv = 1 - amount
    return (
        int(color[0] * inv + target[0] * amount),
        int(color[1] * inv + target[1] * amount),
        int(color[2] * inv + target[2] * amount),
        color[3],
    )


class PixelCanvas:
    def __init__(self, width: int, height: int, background: str = "#ffffff") -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.image = Image.new("RGBA", (self.width, self.height), hex_to_rgba(background))
        self.pixels = self.image.load()
        self.draw = ImageDraw.Draw(self.image, "RGBA")

    def put(self, x: float, y: float, color: tuple[int, int, int, int]) -> None:
        ix = int(round(x))
        iy = int(round(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            if color[3] >= 250:
                self.pixels[ix, iy] = color
            else:
                self.pixels[ix, iy] = blend(self.pixels[ix, iy], color)

    def native_line(self, start: Point, end: Point, color: tuple[int, int, int, int], width: int = 1, dash: str = "solid") -> None:
        fill = color if color[3] >= 250 else flatten_rgba(color)
        if dash == "solid":
            self.draw.line((start.x, start.y, end.x, end.y), fill=fill, width=max(1, width))
            return
        total = max(abs(end.x - start.x), abs(end.y - start.y), 1)
        segments = int(total // 12) + 1
        for i in range(segments):
            if dash == "dotted" and i % 2:
                continue
            if dash == "dashed" and i % 3 == 2:
                continue
            t1 = i / segments
            t2 = min(1.0, (i + 0.65) / segments)
            p1 = Point(start.x + (end.x - start.x) * t1, start.y + (end.y - start.y) * t1)
            p2 = Point(start.x + (end.x - start.x) * t2, start.y + (end.y - start.y) * t2)
            self.draw.line((p1.x, p1.y, p2.x, p2.y), fill=fill, width=max(1, width))

    def rectangle(
        self,
        left: float,
        top: float,
        right: float,
        bottom: float,
        fill: tuple[int, int, int, int] | None = None,
        outline: tuple[int, int, int, int] | None = None,
        width: int = 1,
        dash: str = "solid",
    ) -> None:
        box = (int(round(left)), int(round(top)), int(round(right)), int(round(bottom)))
        if fill:
            self.draw.rectangle(box, fill=fill if fill[3] >= 250 else flatten_rgba(fill))
        if outline:
            points = [Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom), Point(left, top)]
            for i in range(len(points) - 1):
                self.native_line(points[i], points[i + 1], outline, width, dash)

    def line(self, start: Point, end: Point, color: tuple[int, int, int, int], width: int = 1, dash: str = "solid") -> None:
        x0 = int(round(start.x))
        y0 = int(round(start.y))
        x1 = int(round(end.x))
        y1 = int(round(end.y))
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        step = 0
        radius = max(0, width // 2)

        while True:
            draw_pixel = True
            if dash == "dashed":
                draw_pixel = step % 18 < 11
            elif dash == "dotted":
                draw_pixel = step % 8 < 3
            if draw_pixel:
                if radius == 0:
                    self.put(x0, y0, color)
                else:
                    for ox in range(-radius, radius + 1):
                        for oy in range(-radius, radius + 1):
                            if ox * ox + oy * oy <= radius * radius + 1:
                                self.put(x0 + ox, y0 + oy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            step += 1

    def polyline(self, points: list[Point], color: tuple[int, int, int, int], width: int = 1, dash: str = "solid") -> None:
        for i in range(len(points) - 1):
            self.line(points[i], points[i + 1], color, width, dash)

    def polygon_outline(self, points: list[Point], color: tuple[int, int, int, int], width: int = 1, dash: str = "solid") -> None:
        if len(points) < 2:
            return
        self.polyline(points + [points[0]], color, width, dash)

    def fill_polygon(self, points: list[Point], color: tuple[int, int, int, int]) -> None:
        if len(points) < 3:
            return
        min_y = max(0, int(min(point.y for point in points)))
        max_y = min(self.height - 1, int(max(point.y for point in points)))
        for y in range(min_y, max_y + 1):
            intersections: list[float] = []
            j = len(points) - 1
            for i, pi in enumerate(points):
                pj = points[j]
                if (pi.y <= y < pj.y) or (pj.y <= y < pi.y):
                    x = pi.x + (y - pi.y) * (pj.x - pi.x) / ((pj.y - pi.y) or 1e-9)
                    intersections.append(x)
                j = i
            intersections.sort()
            for i in range(0, len(intersections), 2):
                if i + 1 >= len(intersections):
                    break
                x1 = max(0, int(round(intersections[i])))
                x2 = min(self.width - 1, int(round(intersections[i + 1])))
                if x2 >= x1:
                    fill = color if color[3] >= 250 else flatten_rgba(color)
                    self.draw.line((x1, y, x2, y), fill=fill, width=1)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, stroke: tuple[int, int, int, int], width: int = 1) -> None:
        rx = max(1, int(round(abs(rx))))
        ry = max(1, int(round(abs(ry))))
        x = 0
        y = ry
        rx_sq = rx * rx
        ry_sq = ry * ry
        dx = 2 * ry_sq * x
        dy = 2 * rx_sq * y
        p1 = ry_sq - rx_sq * ry + 0.25 * rx_sq
        while dx < dy:
            self._ellipse_points(cx, cy, x, y, stroke, width)
            if p1 < 0:
                x += 1
                dx += 2 * ry_sq
                p1 += dx + ry_sq
            else:
                x += 1
                y -= 1
                dx += 2 * ry_sq
                dy -= 2 * rx_sq
                p1 += dx - dy + ry_sq
        p2 = ry_sq * (x + 0.5) * (x + 0.5) + rx_sq * (y - 1) * (y - 1) - rx_sq * ry_sq
        while y >= 0:
            self._ellipse_points(cx, cy, x, y, stroke, width)
            if p2 > 0:
                y -= 1
                dy -= 2 * rx_sq
                p2 += rx_sq - dy
            else:
                y -= 1
                x += 1
                dx += 2 * ry_sq
                dy -= 2 * rx_sq
                p2 += dx - dy + rx_sq

    def _ellipse_points(self, cx: float, cy: float, x: int, y: int, color: tuple[int, int, int, int], width: int) -> None:
        points = [(cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y), (cx - x, cy - y)]
        radius = max(0, width // 2)
        for px, py in points:
            for ox in range(-radius, radius + 1):
                for oy in range(-radius, radius + 1):
                    self.put(px + ox, py + oy, color)

    def fill_ellipse(self, cx: float, cy: float, rx: float, ry: float, color: tuple[int, int, int, int]) -> None:
        rx = max(1, int(round(abs(rx))))
        ry = max(1, int(round(abs(ry))))
        fill = color if color[3] >= 250 else flatten_rgba(color)
        for y in range(-ry, ry + 1):
            span = int(rx * (1 - (y * y) / (ry * ry)) ** 0.5)
            self.draw.line((cx - span, cy + y, cx + span, cy + y), fill=fill, width=1)


class Renderer:
    def __init__(self) -> None:
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
        self._image_cache: dict[tuple[str, str, int, int], Image.Image] = {}

    def render(
        self,
        document: Document,
        viewport_w: int,
        viewport_h: int,
        zoom: float,
        offset: Point,
        selected: set[str] | None = None,
        show_grid: bool = True,
        marquee: tuple[Point, Point] | None = None,
    ) -> Image.Image:
        selected = selected or set()
        canvas = PixelCanvas(viewport_w, viewport_h, "#ececf8")
        if show_grid:
            self._draw_grid(canvas, document.grid_size, zoom, offset)
        self._draw_page_shadow(canvas, document, zoom, offset)
        self._draw_page(canvas, document, zoom, offset)

        coord_frames = [shape for shape in document.shapes if shape.type == "coord3d"]
        for shape in coord_frames:
            self._draw_coord3d_layer(canvas, shape, zoom, offset, "background")
        for shape in document.shapes:
            if shape.type != "coord3d":
                self._draw_shape(canvas, document, shape, zoom, offset)
        for shape in coord_frames:
            self._draw_coord3d_layer(canvas, shape, zoom, offset, "foreground")
        for shape in document.shapes:
            self._draw_three_d_annotations(canvas, document, shape, zoom, offset)
        for shape in document.shapes:
            if shape.id in selected:
                self._draw_selection(canvas, shape, zoom, offset)
        if marquee:
            self._draw_marquee(canvas, marquee, zoom, offset)
        return canvas.image.convert("RGB")

    def render_document(self, document: Document) -> Image.Image:
        canvas = PixelCanvas(document.width, document.height, document.background)
        coord_frames = [shape for shape in document.shapes if shape.type == "coord3d"]
        for shape in coord_frames:
            self._draw_coord3d_layer(canvas, shape, 1.0, Point(0, 0), "background")
        for shape in document.shapes:
            if shape.type != "coord3d":
                self._draw_shape(canvas, document, shape, 1.0, Point(0, 0))
        for shape in coord_frames:
            self._draw_coord3d_layer(canvas, shape, 1.0, Point(0, 0), "foreground")
        for shape in document.shapes:
            self._draw_three_d_annotations(canvas, document, shape, 1.0, Point(0, 0))
        return canvas.image.convert("RGB")

    def world_to_screen(self, point: Point, zoom: float, offset: Point) -> Point:
        return Point(point.x * zoom + offset.x, point.y * zoom + offset.y)

    def screen_shape(self, shape: Shape, zoom: float, offset: Point) -> Shape:
        copy = replace(shape)
        copy.x = copy.x * zoom + offset.x
        copy.y = copy.y * zoom + offset.y
        copy.w *= zoom
        copy.h *= zoom
        copy.points = [self.world_to_screen(point, zoom, offset) for point in copy.points]
        return copy

    def _draw_grid(self, canvas: PixelCanvas, grid_size: int, zoom: float, offset: Point) -> None:
        spacing = max(8, int(grid_size * zoom))
        color = hex_to_rgba("#d6d7ee", 0.55)
        major = hex_to_rgba("#bcbfe4", 0.62)
        start_x = int(offset.x % spacing)
        start_y = int(offset.y % spacing)
        for x in range(start_x, canvas.width, spacing):
            line_color = major if abs(((x - offset.x) / spacing) % 5) < 0.1 else color
            canvas.native_line(Point(x, 0), Point(x, canvas.height), line_color, 1)
        for y in range(start_y, canvas.height, spacing):
            line_color = major if abs(((y - offset.y) / spacing) % 5) < 0.1 else color
            canvas.native_line(Point(0, y), Point(canvas.width, y), line_color, 1)

    def _draw_page_shadow(self, canvas: PixelCanvas, document: Document, zoom: float, offset: Point) -> None:
        left = offset.x + 8
        top = offset.y + 10
        right = left + document.width * zoom
        bottom = top + document.height * zoom
        canvas.rectangle(left, top, right, bottom, fill=hex_to_rgba("#000000", 0.08))

    def _draw_page(self, canvas: PixelCanvas, document: Document, zoom: float, offset: Point) -> None:
        left = offset.x
        top = offset.y
        right = left + document.width * zoom
        bottom = top + document.height * zoom
        canvas.rectangle(left, top, right, bottom, fill=hex_to_rgba(document.background), outline=hex_to_rgba("#cfd0ea"), width=1)

    def _draw_shape(self, canvas: PixelCanvas, document: Document, shape: Shape, zoom: float, offset: Point) -> None:
        if shape.type == "connector" and shape.connection:
            start = document.shape_by_id(shape.connection.start_id)
            end = document.shape_by_id(shape.connection.end_id)
            if start and end:
                shape.points = connector_points(start, end, shape.connection.style)

        screen = self.screen_shape(shape, zoom, offset)
        if not self._screen_bounds_visible(screen, canvas):
            return
        style = screen.style
        fill = hex_to_rgba(style.fill, style.opacity)
        stroke = hex_to_rgba(style.stroke, style.opacity)
        width = max(1, int(style.width * zoom))

        if screen.type in {"line", "arrow", "connector"}:
            self._draw_line_like(canvas, screen, stroke, width)
            return
        if screen.type == "pen":
            self.draw_pen_path(canvas, screen, stroke, width)
            return
        if screen.type == "image":
            self._draw_image(canvas, screen, stroke, width)
            return
        if screen.type == "ellipse":
            center = screen.center()
            canvas.fill_ellipse(center.x, center.y, abs(screen.w) / 2, abs(screen.h) / 2, fill)
            canvas.ellipse(center.x, center.y, abs(screen.w) / 2, abs(screen.h) / 2, stroke, width)
        elif screen.type in {"rect", "process", "text"}:
            self._draw_polygon_shape(canvas, transformed_rect_points(screen), fill, stroke, width, style.dash)
        elif screen.type in {"round_rect", "terminator", "org_node"}:
            self._draw_round_rect(canvas, screen, fill, stroke, width)
        elif screen.type in {"diamond", "decision"}:
            self._draw_polygon_shape(canvas, self._diamond_points(screen), fill, stroke, width, style.dash)
        elif screen.type == "triangle":
            self._draw_polygon_shape(canvas, self._triangle_points(screen), fill, stroke, width, style.dash)
        elif screen.type == "io":
            self._draw_polygon_shape(canvas, self._io_points(screen), fill, stroke, width, style.dash)
        elif screen.type == "database":
            self._draw_database(canvas, screen, fill, stroke, width)
        elif screen.type == "document":
            self._draw_document(canvas, screen, fill, stroke, width)
        elif screen.type in {"resistor", "capacitor", "battery", "switch", "ground", "led"}:
            self._draw_circuit(canvas, screen, stroke, width)
        elif screen.type in {"cube", "cuboid"}:
            self._draw_prism(canvas, screen, fill, stroke, width)
        elif screen.type == "sphere":
            self._draw_sphere(canvas, screen, fill, stroke, width)
        elif screen.type == "coord3d":
            self._draw_coord3d_layer(canvas, screen, zoom=1.0, offset=Point(0, 0), layer="foreground")
        else:
            self._draw_polygon_shape(canvas, transformed_rect_points(screen), fill, stroke, width, style.dash)

        if screen.text:
            self._draw_text(canvas, screen, screen.text, style)

    def _screen_bounds_visible(self, shape: Shape, canvas: PixelCanvas, margin: int = 96) -> bool:
        left, top, right, bottom = shape.bounds()
        return not (right < -margin or left > canvas.width + margin or bottom < -margin or top > canvas.height + margin)

    def _draw_polygon_shape(
        self,
        canvas: PixelCanvas,
        points: list[Point],
        fill: tuple[int, int, int, int],
        stroke: tuple[int, int, int, int],
        width: int,
        dash: str,
    ) -> None:
        canvas.fill_polygon(points, fill)
        if width > 0:
            canvas.polygon_outline(points, stroke, width, dash)

    def _draw_round_rect(
        self,
        canvas: PixelCanvas,
        shape: Shape,
        fill: tuple[int, int, int, int],
        stroke: tuple[int, int, int, int],
        width: int,
    ) -> None:
        left, top, right, bottom = shape.bounds()
        radius = min(abs(right - left), abs(bottom - top)) * 0.25
        points: list[Point] = []
        for corner, start_angle in [
            (Point(right - radius, top + radius), -90),
            (Point(right - radius, bottom - radius), 0),
            (Point(left + radius, bottom - radius), 90),
            (Point(left + radius, top + radius), 180),
        ]:
            for i in range(9):
                angle = (start_angle + i * 10) * pi / 180
                points.append(Point(corner.x + radius * cos(angle), corner.y + radius * sin(angle)))
        if abs(shape.rotation) > 0.001:
            center = shape.center()
            points = [rotate_point(point, center, shape.rotation) for point in points]
        self._draw_polygon_shape(canvas, points, fill, stroke, width, shape.style.dash)

    def _draw_line_like(self, canvas: PixelCanvas, shape: Shape, stroke: tuple[int, int, int, int], width: int) -> None:
        points = shape.points
        if not points:
            points = [Point(shape.x, shape.y), Point(shape.x + shape.w, shape.y + shape.h)]
        if shape.connection and shape.connection.style == "curve" and len(points) >= 4:
            points = self._bezier(points[0], points[1], points[2], points[3])
        canvas.polyline(points, stroke, width, shape.style.dash)
        if shape.type in {"arrow", "connector"} and len(points) >= 2:
            self._arrow_head(canvas, points[-2], points[-1], stroke, width)

    def _draw_image(self, canvas: PixelCanvas, shape: Shape, stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        target_w = max(1, int(round(abs(right - left))))
        target_h = max(1, int(round(abs(bottom - top))))
        image = self._load_shape_image(shape, target_w, target_h)
        if image:
            if abs(shape.rotation) > 0.001:
                image = image.rotate(-shape.rotation, expand=True, resample=Image.Resampling.BICUBIC)
                center = shape.center()
                paste_x = int(round(center.x - image.width / 2))
                paste_y = int(round(center.y - image.height / 2))
            else:
                paste_x = int(round(left))
                paste_y = int(round(top))
            canvas.image.alpha_composite(image, (paste_x, paste_y))
        else:
            canvas.rectangle(left, top, right, bottom, fill=hex_to_rgba("#f7f9fc"), outline=stroke, width=max(1, width), dash="dashed")
            self._draw_canvas_text(canvas, Point((left + right) / 2, (top + bottom) / 2), "图片缺失", stroke, 12)
        if shape.style.width > 0:
            canvas.polygon_outline(transformed_rect_points(shape), stroke, width)

    def _load_shape_image(self, shape: Shape, width: int, height: int) -> Image.Image | None:
        if not shape.image_data:
            return None
        key = (shape.id, shape.image_data[:40], width, height)
        if key in self._image_cache:
            return self._image_cache[key]
        try:
            raw = b64decode(shape.image_data)
            image = Image.open(BytesIO(raw)).convert("RGBA")
        except (ValueError, OSError, UnidentifiedImageError):
            return None
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        self._image_cache[key] = image
        if len(self._image_cache) > 80:
            self._image_cache.pop(next(iter(self._image_cache)))
        return image

    def _arrow_head(self, canvas: PixelCanvas, start: Point, end: Point, color: tuple[int, int, int, int], width: int) -> None:
        angle = atan2(end.y - start.y, end.x - start.x)
        size = max(10, width * 4)
        left = Point(end.x - size * cos(angle - pi / 6), end.y - size * sin(angle - pi / 6))
        right = Point(end.x - size * cos(angle + pi / 6), end.y - size * sin(angle + pi / 6))
        canvas.fill_polygon([end, left, right], color)

    def _bezier(self, p0: Point, p1: Point, p2: Point, p3: Point, steps: int = 48) -> list[Point]:
        points = []
        for i in range(steps + 1):
            t = i / steps
            mt = 1 - t
            x = mt**3 * p0.x + 3 * mt * mt * t * p1.x + 3 * mt * t * t * p2.x + t**3 * p3.x
            y = mt**3 * p0.y + 3 * mt * mt * t * p1.y + 3 * mt * t * t * p2.y + t**3 * p3.y
            points.append(Point(x, y))
        return points

    def _diamond_points(self, shape: Shape) -> list[Point]:
        left, top, right, bottom = shape.bounds()
        center = shape.center()
        points = [Point(center.x, top), Point(right, center.y), Point(center.x, bottom), Point(left, center.y)]
        if abs(shape.rotation) > 0.001:
            points = [rotate_point(point, center, shape.rotation) for point in points]
        return points

    def _triangle_points(self, shape: Shape) -> list[Point]:
        left, top, right, bottom = shape.bounds()
        center = shape.center()
        points = [Point(center.x, top), Point(right, bottom), Point(left, bottom)]
        if abs(shape.rotation) > 0.001:
            points = [rotate_point(point, center, shape.rotation) for point in points]
        return points

    def _io_points(self, shape: Shape) -> list[Point]:
        left, top, right, bottom = shape.bounds()
        skew = (right - left) * 0.18
        points = [Point(left + skew, top), Point(right, top), Point(right - skew, bottom), Point(left, bottom)]
        if abs(shape.rotation) > 0.001:
            center = shape.center()
            points = [rotate_point(point, center, shape.rotation) for point in points]
        return points

    def _draw_database(self, canvas: PixelCanvas, shape: Shape, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        ellipse_h = max(12, (bottom - top) * 0.18)
        body = [Point(left, top + ellipse_h / 2), Point(right, top + ellipse_h / 2), Point(right, bottom - ellipse_h / 2), Point(left, bottom - ellipse_h / 2)]
        canvas.fill_polygon(body, fill)
        canvas.line(Point(left, top + ellipse_h / 2), Point(left, bottom - ellipse_h / 2), stroke, width)
        canvas.line(Point(right, top + ellipse_h / 2), Point(right, bottom - ellipse_h / 2), stroke, width)
        canvas.fill_ellipse((left + right) / 2, top + ellipse_h / 2, (right - left) / 2, ellipse_h / 2, fill)
        canvas.ellipse((left + right) / 2, top + ellipse_h / 2, (right - left) / 2, ellipse_h / 2, stroke, width)
        canvas.ellipse((left + right) / 2, bottom - ellipse_h / 2, (right - left) / 2, ellipse_h / 2, stroke, width)

    def _draw_document(self, canvas: PixelCanvas, shape: Shape, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        wave = max(10, (bottom - top) * 0.14)
        points = [
            Point(left, top),
            Point(right, top),
            Point(right, bottom - wave),
            Point(left + (right - left) * 0.66, bottom - wave * 0.28),
            Point(left + (right - left) * 0.33, bottom - wave * 1.3),
            Point(left, bottom - wave * 0.55),
        ]
        self._draw_polygon_shape(canvas, points, fill, stroke, width, shape.style.dash)

    def _draw_circuit(self, canvas: PixelCanvas, shape: Shape, stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        mid_y = (top + bottom) / 2
        mid_x = (left + right) / 2
        if shape.type == "resistor":
            canvas.line(Point(left, mid_y), Point(left + 18, mid_y), stroke, width)
            points = [Point(left + 18, mid_y)]
            span = right - left - 36
            for i in range(1, 8):
                x = left + 18 + span * i / 8
                y = mid_y + (-1 if i % 2 else 1) * (bottom - top) * 0.25
                points.append(Point(x, y))
            points.append(Point(right - 18, mid_y))
            canvas.polyline(points, stroke, width)
            canvas.line(Point(right - 18, mid_y), Point(right, mid_y), stroke, width)
        elif shape.type == "capacitor":
            canvas.line(Point(left, mid_y), Point(mid_x - 10, mid_y), stroke, width)
            canvas.line(Point(mid_x - 10, top + 12), Point(mid_x - 10, bottom - 12), stroke, width)
            canvas.line(Point(mid_x + 10, top + 12), Point(mid_x + 10, bottom - 12), stroke, width)
            canvas.line(Point(mid_x + 10, mid_y), Point(right, mid_y), stroke, width)
        elif shape.type == "battery":
            canvas.line(Point(left, mid_y), Point(mid_x - 14, mid_y), stroke, width)
            canvas.line(Point(mid_x - 14, top + 18), Point(mid_x - 14, bottom - 18), stroke, width)
            canvas.line(Point(mid_x + 8, top + 8), Point(mid_x + 8, bottom - 8), stroke, width)
            canvas.line(Point(mid_x + 8, mid_y), Point(right, mid_y), stroke, width)
        elif shape.type == "switch":
            canvas.line(Point(left, mid_y), Point(mid_x - 14, mid_y), stroke, width)
            canvas.line(Point(mid_x + 18, mid_y), Point(right, mid_y), stroke, width)
            canvas.fill_ellipse(mid_x - 14, mid_y, 3, 3, stroke)
            canvas.fill_ellipse(mid_x + 18, mid_y, 3, 3, stroke)
            canvas.line(Point(mid_x - 12, mid_y - 2), Point(mid_x + 12, top + 14), stroke, width)
        elif shape.type == "ground":
            canvas.line(Point(mid_x, top), Point(mid_x, mid_y), stroke, width)
            canvas.line(Point(left + 18, mid_y), Point(right - 18, mid_y), stroke, width)
            canvas.line(Point(left + 28, mid_y + 10), Point(right - 28, mid_y + 10), stroke, width)
            canvas.line(Point(left + 38, mid_y + 20), Point(right - 38, mid_y + 20), stroke, width)
        elif shape.type == "led":
            tri = [Point(left + 22, top + 14), Point(left + 22, bottom - 14), Point(right - 30, mid_y)]
            canvas.polygon_outline(tri, stroke, width)
            canvas.line(Point(right - 28, top + 14), Point(right - 28, bottom - 14), stroke, width)
            canvas.line(Point(left, mid_y), Point(left + 22, mid_y), stroke, width)
            canvas.line(Point(right - 28, mid_y), Point(right, mid_y), stroke, width)
            canvas.line(Point(right - 20, top + 10), Point(right - 6, top), stroke, width)
            canvas.line(Point(right - 12, top + 22), Point(right + 2, top + 12), stroke, width)

    def _draw_prism(self, canvas: PixelCanvas, shape: Shape, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        box_w = abs(right - left)
        box_h = abs(bottom - top)
        if box_w < 4 or box_h < 4:
            return
        depth_ratio = 0.3 if shape.type == "cube" else 0.22
        depth = max(6, min(box_w, box_h) * depth_ratio)
        depth = min(depth, box_w * 0.42, box_h * 0.42)
        raw_points = {
            "ftl": Point(left, top + depth),
            "ftr": Point(right - depth, top + depth),
            "fbr": Point(right - depth, bottom),
            "fbl": Point(left, bottom),
            "btl": Point(left + depth, top),
            "btr": Point(right, top),
            "bbr": Point(right, bottom - depth),
            "bbl": Point(left + depth, bottom - depth),
        }
        points = raw_points
        if abs(shape.rotation) > 0.001:
            center = shape.center()
            points = {key: rotate_point(point, center, shape.rotation) for key, point in raw_points.items()}

        top_face = [points["ftl"], points["ftr"], points["btr"], points["btl"]]
        side_face = [points["ftr"], points["fbr"], points["bbr"], points["btr"]]
        front_face = [points["ftl"], points["ftr"], points["fbr"], points["fbl"]]
        top_fill = tint_rgba(fill, (255, 255, 255), 0.28)
        side_fill = tint_rgba(fill, (0, 0, 0), 0.08)

        self._draw_polygon_shape(canvas, top_face, top_fill, stroke, width, shape.style.dash)
        self._draw_polygon_shape(canvas, side_face, side_fill, stroke, width, shape.style.dash)
        self._draw_polygon_shape(canvas, front_face, fill, stroke, width, shape.style.dash)

        hidden = (stroke[0], stroke[1], stroke[2], max(45, int(stroke[3] * 0.38)))
        for start, end in [(points["btl"], points["bbl"]), (points["bbl"], points["bbr"]), (points["bbl"], points["fbl"])]:
            canvas.line(start, end, hidden, max(1, width - 1), "dashed")

    def _draw_sphere(self, canvas: PixelCanvas, shape: Shape, fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int], width: int) -> None:
        left, top, right, bottom = shape.bounds()
        center = shape.center()
        rx = abs(right - left) / 2
        ry = abs(bottom - top) / 2
        if rx < 2 or ry < 2:
            return
        canvas.fill_ellipse(center.x, center.y, rx, ry, fill)
        guide = (stroke[0], stroke[1], stroke[2], max(55, int(stroke[3] * 0.45)))
        inner_width = max(1, width // 2)
        canvas.ellipse(center.x, center.y, rx * 0.42, ry, guide, inner_width)
        canvas.ellipse(center.x, center.y, rx, ry * 0.34, guide, inner_width)
        canvas.ellipse(center.x, center.y, rx * 0.74, ry * 0.74, guide, inner_width)
        highlight = hex_to_rgba("#ffffff", 0.36)
        canvas.fill_ellipse(center.x - rx * 0.34, center.y - ry * 0.36, rx * 0.18, ry * 0.12, highlight)
        canvas.ellipse(center.x, center.y, rx, ry, stroke, width)

    def _draw_coord3d_layer(self, canvas: PixelCanvas, shape: Shape, zoom: float, offset: Point, layer: str) -> None:
        left, top, right, bottom = shape.bounds()
        box_w = abs(right - left)
        box_h = abs(bottom - top)
        if box_w < 32 or box_h < 32:
            return

        center = shape.center()
        stroke = hex_to_rgba(shape.style.stroke, shape.style.opacity)
        width = max(2, int(shape.style.width * zoom))

        def place(point: Point) -> Point:
            return self.world_to_screen(point, zoom, offset)

        ref = coord3d_reference(shape)
        origin = ref["origin"]
        x_end = ref["x_end"]
        y_end = ref["y_end"]
        z_end = ref["z_end"]
        guide = (stroke[0], stroke[1], stroke[2], max(34, int(stroke[3] * 0.22)))

        x_vec = Point(x_end.x - origin.x, x_end.y - origin.y)
        y_vec = Point(y_end.x - origin.x, y_end.y - origin.y)
        coord_min = getattr(shape, "coord_min", 0)
        coord_max = max(coord_min + 1, getattr(shape, "coord_max", 5))
        labels = list(range(coord_min, coord_max + 1))
        ticks = max(1, coord_max - coord_min)
        if layer == "background":
            for i in range(1, ticks):
                t = i / ticks
                p_x = Point(origin.x + x_vec.x * t, origin.y + x_vec.y * t)
                p_y = Point(origin.x + y_vec.x * t, origin.y + y_vec.y * t)
                canvas.line(place(p_x), place(Point(p_x.x + y_vec.x * 0.58, p_x.y + y_vec.y * 0.58)), guide, 1, "dotted")
                canvas.line(place(p_y), place(Point(p_y.x + x_vec.x * 0.58, p_y.y + x_vec.y * 0.58)), guide, 1, "dotted")
            yz_guide = (stroke[0], stroke[1], stroke[2], max(28, int(stroke[3] * 0.18)))
            z_vec = Point(z_end.x - origin.x, z_end.y - origin.y)
            for i in range(1, ticks):
                t = i / ticks
                p_z = Point(origin.x + z_vec.x * t, origin.y + z_vec.y * t)
                canvas.line(place(p_z), place(Point(p_z.x + y_vec.x * 0.42, p_z.y + y_vec.y * 0.42)), yz_guide, 1, "dotted")
            return

        axis_width = max(2, width)
        self._draw_arrowed_line(canvas, place(origin), place(x_end), stroke, axis_width)
        self._draw_arrowed_line(canvas, place(origin), place(y_end), stroke, axis_width)
        self._draw_arrowed_line(canvas, place(origin), place(z_end), stroke, axis_width)

        tick_color = (stroke[0], stroke[1], stroke[2], max(80, int(stroke[3] * 0.68)))
        self._draw_axis_ticks(canvas, origin, x_end, tick_color, zoom, offset)
        self._draw_axis_ticks(canvas, origin, y_end, tick_color, zoom, offset)
        self._draw_axis_ticks(canvas, origin, z_end, tick_color, zoom, offset)

        label_color = stroke if stroke[3] >= 250 else flatten_rgba(stroke)
        for value in labels:
            if value == 0:
                continue
            t = (value - coord_min) / max(coord_max - coord_min, 1)
            if 0 < t < 1:
                px = Point(origin.x + x_vec.x * t, origin.y + x_vec.y * t)
                py = Point(origin.x + y_vec.x * t, origin.y + y_vec.y * t)
                pz = Point(origin.x + (z_end.x - origin.x) * t, origin.y + (z_end.y - origin.y) * t)
                self._draw_canvas_text(canvas, place(Point(px.x, px.y + 8)), str(value), label_color, 10)
                self._draw_canvas_text(canvas, place(Point(py.x - 8, py.y)), str(value), label_color, 10)
                self._draw_canvas_text(canvas, place(Point(pz.x - 8, pz.y)), str(value), label_color, 10)
        self._draw_canvas_text(canvas, place(Point(x_end.x + 10, x_end.y + 2)), "x", label_color, 14)
        self._draw_canvas_text(canvas, place(Point(y_end.x + 10, y_end.y - 8)), "y", label_color, 14)
        self._draw_canvas_text(canvas, place(Point(z_end.x, z_end.y - 14)), "z", label_color, 14)
        self._draw_canvas_text(canvas, place(Point(origin.x - 12, origin.y + 14)), "O", label_color, 13)

    def _draw_three_d_annotations(self, canvas: PixelCanvas, document: Document, shape: Shape, zoom: float, offset: Point) -> None:
        if shape.type not in {"cube", "cuboid", "sphere"}:
            return
        coords = [item for item in document.shapes if item.type == "coord3d" and item.id != shape.id]
        coord = find_containing_coord(shape, coords)
        if not coord:
            return
        if shape.type in {"cube", "cuboid"}:
            labels = prism_coordinate_labels(shape, coord)
        else:
            labels = sphere_coordinate_labels(shape, coord)
        if not labels:
            return
        screen_center = self.world_to_screen(shape.center(), zoom, offset)
        for label, world_point, coords in labels:
            screen_point = self.world_to_screen(world_point, zoom, offset)
            pos = label_position(screen_point, screen_center, 14)
            text = f"{label}{coordinate_tuple_text(coords)}"
            self._draw_label_text(canvas, pos, text)

    def _draw_arrowed_line(self, canvas: PixelCanvas, start: Point, end: Point, color: tuple[int, int, int, int], width: int) -> None:
        canvas.line(start, end, color, width)
        self._arrow_head(canvas, start, end, color, width)

    def _draw_axis_ticks(self, canvas: PixelCanvas, start: Point, end: Point, color: tuple[int, int, int, int], zoom: float, offset: Point) -> None:
        dx = end.x - start.x
        dy = end.y - start.y
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        nx = -dy / length * 4
        ny = dx / length * 4
        for i in range(1, 5):
            t = i / 5
            point = Point(start.x + dx * t, start.y + dy * t)
            p1 = Point(point.x - nx, point.y - ny)
            p2 = Point(point.x + nx, point.y + ny)
            canvas.line(self.world_to_screen(p1, zoom, offset), self.world_to_screen(p2, zoom, offset), color, 1)

    def _draw_canvas_text(self, canvas: PixelCanvas, point: Point, text: str, color: tuple[int, int, int, int], size: int) -> None:
        draw = ImageDraw.Draw(canvas.image)
        font = self._get_font("Microsoft YaHei", size)
        box = draw.textbbox((0, 0), text, font=font)
        text_w = box[2] - box[0]
        text_h = box[3] - box[1]
        draw.text((point.x - text_w / 2, point.y - text_h / 2), text, fill=color, font=font)

    def _draw_label_text(self, canvas: PixelCanvas, point: Point, text: str) -> None:
        draw = ImageDraw.Draw(canvas.image, "RGBA")
        font = self._get_font("Microsoft YaHei", 11)
        box = draw.textbbox((0, 0), text, font=font)
        text_w = box[2] - box[0]
        text_h = box[3] - box[1]
        left = point.x - text_w / 2 - 3
        top = point.y - text_h / 2 - 2
        right = point.x + text_w / 2 + 3
        bottom = point.y + text_h / 2 + 2
        draw.rounded_rectangle((left, top, right, bottom), radius=3, fill=(255, 255, 255, 214), outline=(206, 207, 234, 195), width=1)
        draw.text((left + 3, top + 1), text, fill=hex_to_rgba("#2d2f4d"), font=font)

    def draw_pen_path(self, canvas: PixelCanvas, shape: Shape, color: tuple[int, int, int, int], width: int) -> None:
        if len(shape.points) < 2:
            if shape.points:
                p = shape.points[0]
                canvas.fill_ellipse(p.x, p.y, max(2, width), max(2, width), color)
            return
        canvas.polyline(shape.points, color, width, "solid")

    def _draw_text(self, canvas: PixelCanvas, shape: Shape, text: str, style: Style) -> None:
        draw = ImageDraw.Draw(canvas.image)
        font = self._get_font(style.font_family, max(9, int(style.font_size * max(0.6, shape.w / max(1, shape.w)))))
        left, top, right, bottom = shape.bounds()
        lines = self._wrap_text(text, max(20, right - left - 14), font)
        line_heights = []
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font)
            line_heights.append(box[3] - box[1])
        total_h = sum(line_heights) + max(0, len(lines) - 1) * 4
        y = top + max(4, ((bottom - top) - total_h) / 2)
        color = hex_to_rgba(style.stroke, style.opacity)
        for line, line_h in zip(lines, line_heights):
            box = draw.textbbox((0, 0), line, font=font)
            text_w = box[2] - box[0]
            x = left + ((right - left) - text_w) / 2
            draw.text((x, y), line, fill=color, font=font)
            y += line_h + 4

    def _wrap_text(self, text: str, max_width: float, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> list[str]:
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            box = draw.textbbox((0, 0), candidate, font=font)
            if box[2] - box[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines or [""]

    def _get_font(self, family: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        key = (family, size)
        if key in self._font_cache:
            return self._font_cache[key]
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for path in candidates:
            try:
                font = ImageFont.truetype(path, size)
                self._font_cache[key] = font
                return font
            except Exception:
                continue
        font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _draw_selection(self, canvas: PixelCanvas, shape: Shape, zoom: float, offset: Point) -> None:
        screen = self.screen_shape(shape, zoom, offset)
        if screen.type in {"line", "arrow", "connector", "pen"} and screen.points:
            points = screen.points
        else:
            points = transformed_rect_points(screen)
        left = min(point.x for point in points)
        top = min(point.y for point in points)
        right = max(point.x for point in points)
        bottom = max(point.y for point in points)
        color = hex_to_rgba("#6c6fd4", 0.95)
        canvas.rectangle(left, top, right, bottom, outline=color, width=1, dash="dashed")
        for point in [Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom)]:
            canvas.rectangle(point.x - 4, point.y - 4, point.x + 4, point.y + 4, fill=hex_to_rgba("#ffffff"), outline=color, width=1)

    def _draw_marquee(self, canvas: PixelCanvas, marquee: tuple[Point, Point], zoom: float, offset: Point) -> None:
        start, end = marquee
        left, right = sorted([start.x, end.x])
        top, bottom = sorted([start.y, end.y])
        canvas.rectangle(left, top, right, bottom, fill=hex_to_rgba("#6c6fd4", 0.08), outline=hex_to_rgba("#6c6fd4", 0.9), width=1, dash="dashed")
