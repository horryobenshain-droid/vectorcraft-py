from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import Connection, Document, Point, Shape, make_shape


@dataclass
class MindNode:
    label: str
    children: list["MindNode"] = field(default_factory=list)
    depth: int = 0
    width: float = 0.0
    height_self: float = 0.0
    subtree_height: float = 0.0
    x: float = 0.0
    y: float = 0.0


LEVEL_STYLES = [
    {"fill": "#1d8a99", "stroke": "#1d8a99", "text_fill": "#ffffff", "font": 18, "padding_x": 24, "padding_y": 14},
    {"fill": "#eef8fa", "stroke": "#1d8a99", "text_fill": "#1d2433", "font": 15, "padding_x": 18, "padding_y": 12},
    {"fill": "#fff4e6", "stroke": "#d1842f", "text_fill": "#1d2433", "font": 13, "padding_x": 14, "padding_y": 10},
    {"fill": "#f4f1ff", "stroke": "#6c55ad", "text_fill": "#1d2433", "font": 12, "padding_x": 12, "padding_y": 8},
    {"fill": "#f2fbef", "stroke": "#4d8a3f", "text_fill": "#1d2433", "font": 12, "padding_x": 10, "padding_y": 8},
]

EDGE_COLORS = ["#1d8a99", "#d1842f", "#6c55ad", "#4d8a3f", "#c33f4a", "#3a4355"]

NUMBER_PREFIX = re.compile(r"^\s*(\d+(?:\.\d+)*)([.、\s]|$)")


def parse_mind_map_text(text: str) -> MindNode:
    """Parse outline text into a tree.

    优先级：
      1. 行首形如 ``1.``、``1.1``、``2.3.4`` 的编号，按点的数量推断深度。
      2. 否则按缩进推断深度（每 2 个空格或一个 Tab 视为一级）。
      3. 行首可携带 -、*、• 等列表标记。
    """
    raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not raw_lines:
        raise ValueError("请输入至少一行内容。")

    parsed: list[tuple[int, str, int | None]] = []
    for line in raw_lines:
        match = re.match(r"^([ \t]*)(.*)$", line)
        if not match:
            continue
        leading, content = match.group(1), match.group(2)
        content = re.sub(r"^[-*•·◦▪▫]+\s*", "", content).strip()
        if not content:
            continue
        indent = 0
        for ch in leading:
            indent += 4 if ch == "\t" else 1

        number_depth: int | None = None
        number_match = NUMBER_PREFIX.match(content)
        if number_match:
            number_depth = number_match.group(1).count(".") + 1
        parsed.append((indent, content, number_depth))

    if not parsed:
        raise ValueError("没有解析到节点。")

    # 决策：如果任意一行含数字编号，就以编号定深度；否则按缩进。
    uses_numbers = any(item[2] is not None for item in parsed)
    if uses_numbers:
        normalized: list[tuple[int, str]] = []
        last_numbered_depth = 0
        last_depth = 0
        for _indent, content, number_depth in parsed:
            if number_depth is not None:
                depth = number_depth
                last_numbered_depth = depth
            else:
                # 无编号 → 作为最近一个带编号行的直接子节点；连续多行无编号则互为兄弟。
                if last_depth > last_numbered_depth:
                    depth = last_depth
                else:
                    depth = last_numbered_depth + 1
            normalized.append((depth, content))
            last_depth = depth
    else:
        indents = sorted({indent for indent, _content, _ in parsed})
        indent_to_depth = {indent: depth for depth, indent in enumerate(indents)}
        normalized = [(indent_to_depth[indent], content) for indent, content, _ in parsed]

    # 把 normalized depth 抬高，让 root（depth=0）保留给虚拟根
    min_depth = min(depth for depth, _ in normalized)
    if min_depth > 0:
        normalized = [(depth - min_depth, content) for depth, content in normalized]

    roots: list[MindNode] = []
    stack: list[MindNode] = []
    for depth, content in normalized:
        node = MindNode(label=content, depth=depth)
        if depth == 0:
            roots.append(node)
            stack = [node]
            continue
        while stack and stack[-1].depth >= depth:
            stack.pop()
        if not stack:
            if not roots:
                placeholder = MindNode(label="思维导图", depth=0)
                roots.append(placeholder)
                stack = [placeholder]
            else:
                stack = [roots[-1]]
        # 自动补齐缺失的中间层（如直接从 1 跳到 3）
        while stack[-1].depth + 1 < depth:
            filler = MindNode(label=" ", depth=stack[-1].depth + 1)
            stack[-1].children.append(filler)
            stack.append(filler)
        parent = stack[-1]
        parent.children.append(node)
        stack.append(node)

    if len(roots) == 1:
        return roots[0]
    virtual = MindNode(label="思维导图", depth=0)
    for root in roots:
        _shift_depth(root, 1)
        virtual.children.append(root)
    return virtual


def _shift_depth(node: MindNode, delta: int) -> None:
    node.depth += delta
    for child in node.children:
        _shift_depth(child, delta)


MAX_CHILDREN_PER_COLUMN = 14


def mind_map_document(root: MindNode) -> Document:
    """Build a horizontal tree layout with column-chunking for very wide layers."""
    _split_wide_layers(root)
    _measure(root)
    v_gap = 22
    h_gap = 160

    _assign_y(root, 0.0, v_gap)
    _assign_x(root, 0.0, h_gap)

    min_x, min_y, max_x, max_y = _tree_bounds(root)
    margin = 120
    title_h = 80
    offset_x = margin - min_x
    offset_y = margin + title_h - min_y
    _shift(root, offset_x, offset_y)

    width = int(max(1600, (max_x - min_x) + margin * 2 + 220))
    height = int(max(900, (max_y - min_y) + margin * 2 + title_h))
    doc = Document(width=width, height=height)

    title = make_shape("text", margin, 32, max(400, width - margin * 2), 56)
    title.text = "思维导图：" + root.label
    title.style.fill = "#fff7d6"
    title.style.stroke = "#d1842f"
    title.style.font_size = 22
    doc.shapes.append(title)

    nodes_by_id: dict[int, Shape] = {}
    _emit_nodes(doc, root, nodes_by_id)
    _emit_edges(doc, root, nodes_by_id)
    return doc


def _split_wide_layers(node: MindNode) -> None:
    """如果某个父节点直接有很多子节点，按组拆成多个中间节点，避免出现一条很长的列。"""
    for child in node.children:
        _split_wide_layers(child)
    if len(node.children) <= MAX_CHILDREN_PER_COLUMN:
        return
    chunk = max(6, (len(node.children) + 1) // 2)
    new_children: list[MindNode] = []
    for index in range(0, len(node.children), chunk):
        group = node.children[index : index + chunk]
        if len(group) == 1:
            new_children.append(group[0])
            continue
        wrapper = MindNode(label=f"分组 {index // chunk + 1}", depth=node.depth + 1)
        for item in group:
            _shift_depth(item, 1)
            wrapper.children.append(item)
        new_children.append(wrapper)
    node.children = new_children


def _measure(node: MindNode) -> None:
    style = LEVEL_STYLES[min(node.depth, len(LEVEL_STYLES) - 1)]
    label = node.label or " "
    label_len = max(2.0, _visual_length(label))
    node.width = min(360, max(120, label_len * style["font"] * 0.62 + style["padding_x"] * 2))
    node.height_self = style["font"] * 1.7 + style["padding_y"] * 2
    for child in node.children:
        _measure(child)
    if node.children:
        children_height = sum(child.subtree_height for child in node.children) + 24 * (len(node.children) - 1)
        node.subtree_height = max(children_height, node.height_self)
    else:
        node.subtree_height = node.height_self


def _visual_length(text: str) -> float:
    length = 0.0
    for ch in text:
        length += 1.0 if ord(ch) < 128 else 1.7
    return length


def _assign_y(node: MindNode, top: float, gap: float) -> None:
    """Reingold–Tilford 风格的轮廓合并布局（紧凑、可证明同深度不重叠）。

    与朴素的「按子树包围盒高度顺序堆叠」不同，这里逐个兄弟子树只下移到
    「上一批兄弟的下轮廓」恰好让出 gap 的位置——比较的是逐深度的实际轮廓，
    而不是整棵子树的高度，因此能把不规则形状的子树咬合得更紧。
    布局完成后整棵树再平移到 ``top`` 起始。
    """
    _layout_relative(node, gap)
    # 把根（及整棵树）平移，使最上沿对齐到 top。
    top_edge = min(_top_contour(node).values())
    _shift_subtree_y(node, top - top_edge)


def _layout_relative(node: MindNode, gap: float) -> None:
    """后序遍历：先在各孩子的局部坐标里排好，再用轮廓把兄弟咬合在一起。"""
    if not node.children:
        node.y = 0.0
        return

    for child in node.children:
        _layout_relative(child, gap)

    # 逐个把后续兄弟下移，直到其上轮廓与已放置兄弟的下轮廓拉开 gap。
    accumulated_bottom: dict[int, float] = {}
    for index, child in enumerate(node.children):
        if index == 0:
            shift = 0.0
        else:
            child_top = _top_contour(child)
            shift = 0.0
            for depth, bottom in accumulated_bottom.items():
                if depth in child_top:
                    shift = max(shift, bottom + gap - child_top[depth])
        if shift:
            _shift_subtree_y(child, shift)
        for depth, bottom in _bottom_contour(child).items():
            if depth not in accumulated_bottom or bottom > accumulated_bottom[depth]:
                accumulated_bottom[depth] = bottom

    # 父节点居中于首末孩子之间。
    node.y = (node.children[0].y + node.children[-1].y) / 2


def _top_contour(node: MindNode, depth: int = 0, acc: dict[int, float] | None = None) -> dict[int, float]:
    """每个相对深度上的最小上沿（node.y - height_self/2）。"""
    if acc is None:
        acc = {}
    top = node.y - node.height_self / 2
    if depth not in acc or top < acc[depth]:
        acc[depth] = top
    for child in node.children:
        _top_contour(child, depth + 1, acc)
    return acc


def _bottom_contour(node: MindNode, depth: int = 0, acc: dict[int, float] | None = None) -> dict[int, float]:
    """每个相对深度上的最大下沿（node.y + height_self/2）。"""
    if acc is None:
        acc = {}
    bottom = node.y + node.height_self / 2
    if depth not in acc or bottom > acc[depth]:
        acc[depth] = bottom
    for child in node.children:
        _bottom_contour(child, depth + 1, acc)
    return acc


def _shift_subtree_y(node: MindNode, dy: float) -> None:
    node.y += dy
    for child in node.children:
        _shift_subtree_y(child, dy)


def _assign_x(node: MindNode, x: float, h_gap: float) -> None:
    node.x = x
    for child in node.children:
        _assign_x(child, x + node.width + h_gap, h_gap)


def _tree_bounds(node: MindNode) -> tuple[float, float, float, float]:
    xs = [node.x, node.x + node.width]
    ys = [node.y - node.height_self / 2, node.y + node.height_self / 2]
    for child in node.children:
        cx0, cy0, cx1, cy1 = _tree_bounds(child)
        xs.extend([cx0, cx1])
        ys.extend([cy0, cy1])
    return min(xs), min(ys), max(xs), max(ys)


def _shift(node: MindNode, dx: float, dy: float) -> None:
    node.x += dx
    node.y += dy
    for child in node.children:
        _shift(child, dx, dy)


def _emit_nodes(doc: Document, node: MindNode, registry: dict[int, Shape]) -> None:
    style = LEVEL_STYLES[min(node.depth, len(LEVEL_STYLES) - 1)]
    top = node.y - node.height_self / 2
    shape = make_shape("round_rect", node.x, top, node.width, node.height_self)
    shape.text = node.label
    shape.style.fill = style["fill"]
    shape.style.stroke = style["stroke"]
    shape.style.font_size = style["font"]
    if node.depth == 0:
        shape.style.width = 2
    doc.shapes.append(shape)
    registry[id(node)] = shape
    for child in node.children:
        _emit_nodes(doc, child, registry)


def _emit_edges(doc: Document, node: MindNode, registry: dict[int, Shape]) -> None:
    parent_shape = registry[id(node)]
    for child in node.children:
        child_shape = registry[id(child)]
        connector = make_shape("connector", 0, 0, 0, 0)
        connector.connection = Connection(parent_shape.id, child_shape.id, "curve")
        connector.style.stroke = EDGE_COLORS[node.depth % len(EDGE_COLORS)]
        connector.style.width = max(2, 3 - node.depth)
        doc.shapes.append(connector)
        _emit_edges(doc, child, registry)


def generate_mind_map_from_text(text: str) -> Document:
    root = parse_mind_map_text(text)
    return mind_map_document(root)
