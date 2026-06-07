from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4


ShapeType = Literal[
    "rect",
    "round_rect",
    "ellipse",
    "diamond",
    "triangle",
    "line",
    "arrow",
    "pen",
    "text",
    "terminator",
    "process",
    "decision",
    "io",
    "database",
    "document",
    "org_node",
    "resistor",
    "capacitor",
    "battery",
    "switch",
    "ground",
    "led",
    "connector",
    "cube",
    "cuboid",
    "sphere",
    "coord3d",
    "image",
]


@dataclass
class Point:
    x: float
    y: float

    def copy(self) -> "Point":
        return Point(self.x, self.y)

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Style:
    fill: str = "#f7fbff"
    stroke: str = "#1f2a44"
    width: int = 2
    opacity: float = 1.0
    dash: str = "solid"
    font_size: int = 16
    font_family: str = "Microsoft YaHei"


@dataclass
class Connection:
    start_id: str | None = None
    end_id: str | None = None
    style: str = "orthogonal"


@dataclass
class Shape:
    type: ShapeType
    x: float
    y: float
    w: float
    h: float
    id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    text: str = ""
    points: list[Point] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    connection: Connection | None = None
    coord_min: int = 0
    coord_max: int = 5
    locked: bool = False
    image_data: str = ""
    image_mime: str = "image/png"
    image_path: str = ""
    source_url: str = ""

    def clone(self, dx: float = 24, dy: float = 24) -> "Shape":
        data = self.to_dict()
        data["id"] = uuid4().hex
        data["x"] += dx
        data["y"] += dy
        data["points"] = [{"x": p["x"] + dx, "y": p["y"] + dy} for p in data.get("points", [])]
        return Shape.from_dict(data)

    def bounds(self) -> tuple[float, float, float, float]:
        if self.points:
            xs = [point.x for point in self.points]
            ys = [point.y for point in self.points]
            return min(xs), min(ys), max(xs), max(ys)
        x2 = self.x + self.w * self.scale_x
        y2 = self.y + self.h * self.scale_y
        return min(self.x, x2), min(self.y, y2), max(self.x, x2), max(self.y, y2)

    def center(self) -> Point:
        left, top, right, bottom = self.bounds()
        return Point((left + right) / 2, (top + bottom) / 2)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        for point in self.points:
            point.x += dx
            point.y += dy

    def resize_from_bounds(self, left: float, top: float, right: float, bottom: float) -> None:
        self.x = left
        self.y = top
        self.w = max(4, right - left)
        self.h = max(4, bottom - top)
        if self.points and self.type in {"line", "arrow", "connector"}:
            self.points = [Point(left, top), Point(right, bottom)]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["points"] = [asdict(point) for point in self.points]
        data["style"] = asdict(self.style)
        data["connection"] = asdict(self.connection) if self.connection else None
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Shape":
        item = dict(data)
        item["points"] = [Point(**point) for point in item.get("points", [])]
        style = item.get("style") or {}
        item["style"] = Style(**style)
        connection = item.get("connection")
        item["connection"] = Connection(**connection) if connection else None
        return Shape(**item)


@dataclass
class Document:
    width: int = 1800
    height: int = 1200
    background: str = "#ffffff"
    grid_size: int = 24
    shapes: list[Shape] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": "VectorCraft-Py",
            "version": "1.0",
            "canvas": {
                "width": self.width,
                "height": self.height,
                "background": self.background,
                "grid_size": self.grid_size,
            },
            "shapes": [shape.to_dict() for shape in self.shapes],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Document":
        canvas = data.get("canvas", {})
        return Document(
            width=int(canvas.get("width", 1800)),
            height=int(canvas.get("height", 1200)),
            background=canvas.get("background", "#ffffff"),
            grid_size=int(canvas.get("grid_size", 24)),
            shapes=[Shape.from_dict(shape) for shape in data.get("shapes", [])],
        )

    def shape_by_id(self, shape_id: str | None) -> Shape | None:
        if not shape_id:
            return None
        for shape in self.shapes:
            if shape.id == shape_id:
                return shape
        return None

    def remove_ids(self, ids: set[str]) -> None:
        self.shapes = [shape for shape in self.shapes if shape.id not in ids]
        for shape in self.shapes:
            if shape.connection:
                if shape.connection.start_id in ids:
                    shape.connection.start_id = None
                if shape.connection.end_id in ids:
                    shape.connection.end_id = None

    def copy(self) -> "Document":
        return Document.from_dict(self.to_dict())


DEFAULT_LABELS: dict[str, str] = {
    "image": "在线图形",
    "rect": "矩形",
    "round_rect": "圆角矩形",
    "ellipse": "椭圆",
    "diamond": "菱形",
    "triangle": "三角形",
    "line": "直线",
    "arrow": "箭头",
    "pen": "画笔",
    "text": "文本",
    "terminator": "开始/结束",
    "process": "处理",
    "decision": "判断",
    "io": "输入/输出",
    "database": "数据库",
    "document": "文档",
    "org_node": "组织节点",
    "resistor": "电阻",
    "capacitor": "电容",
    "battery": "电池",
    "switch": "开关",
    "ground": "接地",
    "led": "LED",
    "connector": "连接线",
    "cube": "正方体",
    "cuboid": "长方体",
    "sphere": "球体",
    "coord3d": "三维坐标系",
}


def make_shape(shape_type: ShapeType, x: float, y: float, w: float = 120, h: float = 72) -> Shape:
    label = DEFAULT_LABELS.get(shape_type, shape_type)
    style = Style()
    text = ""
    points: list[Point] = []
    connection = None

    if shape_type in {"cube", "sphere"}:
        size = max(abs(w), abs(h), 24)
        w = size if w >= 0 else -size
        h = size if h >= 0 else -size

    if shape_type in {"line", "arrow", "connector"}:
        points = [Point(x, y), Point(x + w, y + h)]
        style.fill = "#ffffff"
        connection = Connection(style="orthogonal") if shape_type == "connector" else None
    elif shape_type == "pen":
        points = [Point(x, y)]
        style.fill = "#ffffff"
        style.stroke = "#1f2a44"
        style.width = 3
    elif shape_type == "text":
        text = "双击编辑文本"
        style.fill = "#fff7d6"
        style.stroke = "#d1842f"
    elif shape_type in {"terminator", "process", "decision", "io", "database", "document", "org_node"}:
        text = label
        style.fill = "#eef8fa"
        style.stroke = "#1d8a99"
    elif shape_type in {"resistor", "capacitor", "battery", "switch", "ground", "led"}:
        style.fill = "#ffffff"
        style.stroke = "#263346"
    elif shape_type in {"cube", "cuboid", "sphere"}:
        style.fill = "#eef8fa"
        style.stroke = "#24515c"
        style.opacity = 0.92
    elif shape_type == "coord3d":
        style.fill = "#ffffff"
        style.stroke = "#263346"
        style.width = 2
    elif shape_type == "image":
        style.fill = "#ffffff"
        style.stroke = "#8b97a8"
        style.width = 1
    elif shape_type == "diamond":
        text = ""
        style.fill = "#fff4e6"
        style.stroke = "#d1842f"
    elif shape_type == "triangle":
        style.fill = "#f4f1ff"
        style.stroke = "#6c55ad"

    return Shape(
        type=shape_type,
        name=label,
        x=x,
        y=y,
        w=w,
        h=h,
        text=text,
        points=points,
        style=style,
        connection=connection,
    )
