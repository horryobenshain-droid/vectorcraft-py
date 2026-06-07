from __future__ import annotations

from collections import defaultdict, deque
import re

from .geometry import snap
from .model import Connection, Document, Shape, make_shape


BRANCH_LABELS = {"是", "否", "yes", "no", "true", "false", "y", "n"}
ARROW_PATTERN = re.compile(r"\s*(?:->|-->|=>|→|⇒)\s*")


def generate_flowchart_from_text(text: str) -> Document:
    """Build a flowchart document from arrow-style Chinese text."""
    lines = [_normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("请输入至少一行流程描述。")

    node_order: list[str] = []
    edges: list[tuple[str, str, str]] = []
    current_decision: str | None = None

    for line in lines:
        parts = [_clean_token(part) for part in ARROW_PATTERN.split(line)]
        parts = [part for part in parts if part]
        if not parts:
            continue

        first = parts[0].lower()
        if first in BRANCH_LABELS and current_decision and len(parts) >= 2:
            branch_label = _branch_text(parts[0])
            _add_node(node_order, current_decision)
            _add_node(node_order, parts[1])
            edges.append((current_decision, parts[1], branch_label))
            for start, end in zip(parts[1:], parts[2:]):
                _add_node(node_order, start)
                _add_node(node_order, end)
                edges.append((start, end, ""))
            if parts[1:]:
                decision = _last_decision(parts[1:])
                if decision:
                    current_decision = decision
            continue

        for part in parts:
            _add_node(node_order, part)
        for start, end in zip(parts, parts[1:]):
            edges.append((start, end, ""))

        decision = _last_decision(parts)
        if decision:
            current_decision = decision

    if not node_order:
        raise ValueError("没有识别到可生成的流程节点。")

    doc = Document(height=max(900, 250 + max(1, len(node_order)) * 86))
    title = make_shape("text", 560, 32, 680, 56)
    title.text = "文本自动生成流程图"
    title.style.fill = "#fff7d6"
    title.style.stroke = "#d1842f"
    title.style.font_size = 20
    doc.shapes.append(title)

    levels = _compute_levels(node_order, edges)
    rows: dict[int, list[str]] = defaultdict(list)
    for label in node_order:
        rows[levels.get(label, 0)].append(label)

    max_level = max(rows) if rows else 0
    doc.height = max(900, 260 + (max_level + 1) * 150)
    if any(len(row) >= 5 for row in rows.values()):
        doc.width = max(doc.width, 2200)

    shapes_by_label: dict[str, Shape] = {}
    for level in sorted(rows):
        row = rows[level]
        gap_x = 360 if len(row) <= 3 else 290
        row_width = (len(row) - 1) * gap_x
        start_center_x = doc.width / 2 - row_width / 2
        center_y = 145 + level * 150
        for index, label in enumerate(row):
            shape = _make_node(label)
            center_x = start_center_x + index * gap_x
            shape.x = snap(center_x - shape.w / 2, doc.grid_size)
            shape.y = snap(center_y - shape.h / 2, doc.grid_size)
            shapes_by_label[label] = shape
            doc.shapes.append(shape)

    for start, end, branch_label in edges:
        if start not in shapes_by_label or end not in shapes_by_label:
            continue
        connector = make_shape("connector", 0, 0, 0, 0)
        connector.connection = Connection(shapes_by_label[start].id, shapes_by_label[end].id, "orthogonal")
        connector.style.stroke = "#263346"
        connector.style.width = 2
        doc.shapes.append(connector)
        if branch_label:
            doc.shapes.append(_edge_label(branch_label, shapes_by_label[start], shapes_by_label[end]))

    return doc


def _normalize_line(line: str) -> str:
    line = line.strip()
    line = line.replace("：", ":")
    line = re.sub(r"^(是|否|yes|no|true|false|Y|N)\s*:", r"\1 -> ", line, flags=re.IGNORECASE)
    return line


def _clean_token(token: str) -> str:
    token = token.strip(" \t;；,，")
    return re.sub(r"\s+", " ", token)


def _branch_text(label: str) -> str:
    lowered = label.lower()
    if lowered in {"yes", "true", "y"}:
        return "是"
    if lowered in {"no", "false", "n"}:
        return "否"
    return label


def _add_node(order: list[str], label: str) -> None:
    if label not in order:
        order.append(label)


def _last_decision(parts: list[str]) -> str | None:
    for part in reversed(parts):
        if _infer_shape_type(part) == "decision":
            return part
    return None


def _infer_shape_type(label: str) -> str:
    compact = label.replace(" ", "")
    if "开始" in compact or compact.lower() in {"start", "begin"}:
        return "terminator"
    if "结束" in compact or "终止" in compact or compact.lower() in {"end", "finish", "stop"}:
        return "terminator"
    if compact.endswith("?") or compact.endswith("？") or "是否" in compact or "判断" in compact:
        return "decision"
    if any(word in compact for word in ["输入", "输出", "读取", "接收", "导入", "导出"]):
        return "io"
    if any(word in compact for word in ["保存", "数据库", "记录", "入库"]):
        return "database"
    if any(word in compact for word in ["报表", "文档", "清单", "报告"]):
        return "document"
    return "process"


def _make_node(label: str) -> Shape:
    shape_type = _infer_shape_type(label)
    w = max(170, min(340, 90 + len(label) * 16))
    h = 76
    if shape_type == "decision":
        w = max(220, min(360, 110 + len(label) * 15))
        h = 112
    elif shape_type == "terminator":
        w = max(190, min(320, 90 + len(label) * 16))
        h = 64
    elif shape_type == "database":
        h = 86
    elif shape_type == "document":
        h = 84

    shape = make_shape(shape_type, 0, 0, w, h)
    shape.text = label
    shape.style.width = 2
    shape.style.font_size = 16
    if shape_type == "decision":
        shape.style.fill = "#fff4e6"
        shape.style.stroke = "#d1842f"
    elif shape_type == "terminator":
        shape.style.fill = "#e9f8fb"
        shape.style.stroke = "#1d8a99"
    elif shape_type == "database":
        shape.style.fill = "#f2fbef"
        shape.style.stroke = "#4d8a3f"
    elif shape_type == "document":
        shape.style.fill = "#fff7d6"
        shape.style.stroke = "#d1842f"
    else:
        shape.style.fill = "#eef8fa"
        shape.style.stroke = "#1d8a99"
    return shape


def _compute_levels(node_order: list[str], edges: list[tuple[str, str, str]]) -> dict[str, int]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree = {label: 0 for label in node_order}
    for start, end, _label in edges:
        adjacency[start].append(end)
        indegree[end] = indegree.get(end, 0) + 1
        indegree.setdefault(start, 0)

    sources = [label for label in node_order if indegree.get(label, 0) == 0]
    if not sources and node_order:
        sources = [node_order[0]]

    levels = {label: 0 for label in sources}
    queue: deque[str] = deque(sources)
    visited_count = 0
    while queue:
        start = queue.popleft()
        visited_count += 1
        for end in adjacency.get(start, []):
            levels[end] = max(levels.get(end, 0), levels.get(start, 0) + 1)
            indegree[end] -= 1
            if indegree[end] <= 0:
                queue.append(end)

    if visited_count < len(node_order):
        last_level = 0
        for label in node_order:
            if label in levels:
                last_level = max(last_level, levels[label])
            else:
                last_level += 1
                levels[label] = last_level
    return levels


def _edge_label(text: str, start: Shape, end: Shape) -> Shape:
    start_center = start.center()
    end_center = end.center()
    label = make_shape("text", (start_center.x + end_center.x) / 2 - 24, (start_center.y + end_center.y) / 2 - 18, 48, 30)
    label.text = text
    label.style.fill = "#ffffff"
    label.style.stroke = "#526072"
    label.style.width = 1
    label.style.font_size = 14
    return label
