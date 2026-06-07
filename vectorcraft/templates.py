from __future__ import annotations

import math
import re

from .model import Connection, Document, Point, Shape, make_shape


DIAGRAM_PALETTE = ["#1d8a99", "#d1842f", "#6c55ad", "#4d8a3f", "#c33f4a", "#3a4355", "#207e6b"]


def flowchart_template() -> Document:
    doc = Document(height=1280)
    title = _node("text", 600, 34, 600, 58, "数据处理与报表生成流程", "#fff7d6", "#d1842f")
    start = _node("terminator", 780, 120, 240, 64, "开始", "#e9f8fb", "#1d8a99")
    collect = _node("io", 750, 220, 300, 76, "接收原始数据", "#eef8fa", "#1d8a99")
    validate = _node("decision", 785, 340, 230, 126, "数据完整?", "#fff4e6", "#d1842f")
    clean = _node("process", 750, 520, 300, 76, "清洗与标准化", "#eef8fa", "#1d8a99")
    approve = _node("decision", 785, 640, 230, 126, "需要审批?", "#fff4e6", "#d1842f")
    review = _node("process", 420, 660, 270, 74, "人工复核与审批", "#f4f1ff", "#6c55ad")
    generate = _node("process", 750, 815, 300, 76, "生成统计图表", "#eef8fa", "#1d8a99")
    database = _node("database", 750, 930, 300, 88, "保存处理记录", "#f2fbef", "#4d8a3f")
    report = _node("document", 750, 1050, 300, 86, "导出报表 / SVG / PNG", "#fff7d6", "#d1842f")
    end = _node("terminator", 780, 1180, 240, 64, "结束", "#e9f8fb", "#1d8a99")

    error_report = _node("document", 1120, 365, 300, 86, "生成错误清单", "#fff2f3", "#c33f4a")
    notify = _node("process", 1120, 505, 300, 76, "通知用户补充数据", "#fff2f3", "#c33f4a")
    stop = _node("terminator", 1150, 640, 240, 64, "异常结束", "#fff2f3", "#c33f4a")

    doc.shapes.extend([title, start, collect, validate, clean, approve, review, generate, database, report, end, error_report, notify, stop])
    _connect(doc, start, collect)
    _connect(doc, collect, validate)
    _connect(doc, validate, clean)
    _connect(doc, validate, error_report)
    _connect(doc, error_report, notify)
    _connect(doc, notify, stop)
    _connect(doc, clean, approve)
    _connect(doc, approve, review)
    _connect(doc, review, generate)
    _connect(doc, approve, generate)
    _connect(doc, generate, database)
    _connect(doc, database, report)
    _connect(doc, report, end)

    doc.shapes.extend(
        [
            _label("是", 870, 480),
            _label("否", 1030, 365),
            _label("是", 690, 650),
            _label("否", 870, 770),
        ]
    )
    return doc


def org_template() -> Document:
    doc = Document(height=980)
    title = _node("text", 610, 38, 580, 58, "VectorCraft 项目组织结构图", "#fff7d6", "#d1842f")
    lead = _node("org_node", 780, 125, 240, 76, "项目负责人", "#e9f8fb", "#1d8a99")

    product = _node("org_node", 120, 280, 220, 74, "产品设计组", "#eef8fa", "#1d8a99")
    algo = _node("org_node", 450, 280, 220, 74, "图形算法组", "#eef8fa", "#1d8a99")
    ui = _node("org_node", 780, 280, 220, 74, "界面交互组", "#eef8fa", "#1d8a99")
    storage = _node("org_node", 1110, 280, 220, 74, "存储导出组", "#eef8fa", "#1d8a99")
    qa = _node("org_node", 1440, 280, 220, 74, "测试文档组", "#eef8fa", "#1d8a99")

    children = [
        _node("org_node", 40, 455, 160, 66, "需求分析", "#f7fbff", "#526f8a"),
        _node("org_node", 215, 455, 160, 66, "模板规划", "#f7fbff", "#526f8a"),
        _node("org_node", 390, 455, 160, 66, "直线/裁剪", "#f7fbff", "#526f8a"),
        _node("org_node", 565, 455, 160, 66, "填充/曲线", "#f7fbff", "#526f8a"),
        _node("org_node", 740, 455, 160, 66, "画布交互", "#f7fbff", "#526f8a"),
        _node("org_node", 915, 455, 160, 66, "属性面板", "#f7fbff", "#526f8a"),
        _node("org_node", 1090, 455, 160, 66, "JSON 工程", "#f7fbff", "#526f8a"),
        _node("org_node", 1265, 455, 160, 66, "SVG 导出", "#f7fbff", "#526f8a"),
        _node("org_node", 1440, 455, 160, 66, "功能测试", "#f7fbff", "#526f8a"),
        _node("org_node", 1615, 455, 160, 66, "报告整理", "#f7fbff", "#526f8a"),
    ]

    milestones = [
        _node("document", 360, 660, 260, 74, "核心算法说明", "#fff7d6", "#d1842f"),
        _node("document", 770, 660, 260, 74, "可运行演示程序", "#fff7d6", "#d1842f"),
        _node("document", 1180, 660, 260, 74, "工程文件与导出样例", "#fff7d6", "#d1842f"),
    ]

    doc.shapes.extend([title, lead, product, algo, ui, storage, qa, *children, *milestones])
    for group in [product, algo, ui, storage, qa]:
        _connect(doc, lead, group)
    pairs = [
        (product, children[0]),
        (product, children[1]),
        (algo, children[2]),
        (algo, children[3]),
        (ui, children[4]),
        (ui, children[5]),
        (storage, children[6]),
        (storage, children[7]),
        (qa, children[8]),
        (qa, children[9]),
    ]
    for parent, child in pairs:
        _connect(doc, parent, child)
    return doc


def circuit_template() -> Document:
    doc = Document(height=980)
    title = _node("text", 590, 70, 620, 62, "带保护与滤波支路的 LED 指示电路", "#fff7d6", "#d1842f")
    battery = _node("battery", 230, 340, 110, 80, "", "#ffffff", "#263346")
    switch = _node("switch", 440, 340, 130, 80, "", "#ffffff", "#263346")
    resistor = _node("resistor", 660, 340, 160, 80, "", "#ffffff", "#263346")
    led = _node("led", 930, 340, 150, 80, "", "#ffffff", "#263346")
    meter = _node("ellipse", 1160, 334, 92, 92, "A", "#f7fbff", "#263346")
    ground = _node("ground", 1370, 520, 110, 80, "", "#ffffff", "#263346")
    capacitor = _node("capacitor", 680, 545, 150, 78, "", "#ffffff", "#263346")
    branch_resistor = _node("resistor", 930, 545, 150, 78, "", "#ffffff", "#263346")
    branch_ground = _node("ground", 960, 700, 110, 80, "", "#ffffff", "#263346")

    doc.shapes.extend([title, battery, switch, resistor, led, meter, ground, capacitor, branch_resistor, branch_ground])
    wire_color = "#263346"
    doc.shapes.extend(
        [
            _wire([(150, 380), (230, 380)], wire_color),
            _wire([(340, 380), (440, 380)], wire_color),
            _wire([(570, 380), (660, 380)], wire_color),
            _wire([(820, 380), (930, 380)], wire_color),
            _wire([(1080, 380), (1160, 380)], wire_color),
            _wire([(1252, 380), (1425, 380), (1425, 520)], wire_color),
            _wire([(615, 380), (615, 584), (680, 584)], wire_color),
            _wire([(830, 584), (930, 584)], wire_color),
            _wire([(1080, 584), (1160, 584), (1160, 380)], wire_color),
            _wire([(1005, 623), (1005, 700)], wire_color),
        ]
    )
    doc.shapes.extend(
        [
            _label("+5V", 145, 332, 80),
            _label("电源", 235, 445, 90),
            _label("开关 S1", 438, 445, 120),
            _label("限流电阻 R1", 650, 445, 150),
            _label("LED 指示灯", 928, 445, 150),
            _label("电流表", 1150, 445, 120),
            _label("滤波电容 C1", 670, 635, 150),
            _label("泄放电阻 R2", 920, 635, 150),
            _label("公共地", 1360, 615, 120),
        ]
    )
    return doc


DEFAULT_UML_CLASSES = [
    ("Shape",
     ["id: str", "type: ShapeType", "x, y, w, h: float", "rotation: float", "text: str", "style: Style", "points: List[Point]"],
     ["bounds(): Rect", "center(): Point", "move(dx, dy)", "clone(): Shape", "to_dict(): dict"]),
    ("Style",
     ["fill: str", "stroke: str", "width: int", "opacity: float", "dash: str", "font_size: int"],
     []),
    ("Point", ["x: float", "y: float"], ["copy(): Point", "to_tuple(): tuple"]),
    ("Connection", ["start_id: str", "end_id: str", "style: str"], []),
    ("Document",
     ["width, height: int", "background: str", "grid_size: int", "shapes: List[Shape]"],
     ["to_dict(): dict", "shape_by_id(id): Shape", "remove_ids(ids)", "copy(): Document"]),
    ("Page", ["name: str", "document: Document"], ["rename(name)"]),
    ("History", ["limit: int", "undo_stack: List", "redo_stack: List"],
     ["push(doc)", "undo(doc): Document", "redo(doc): Document"]),
    ("Renderer", ["font_cache: dict", "image_cache: dict"],
     ["render(doc, ...): Image", "export_png(doc, path)"]),
]

DEFAULT_UML_RELATIONS = [
    ("Document", "Shape", "聚合 0..*", False),
    ("Page", "Document", "组合 1", False),
    ("Shape", "Style", "组合 1", False),
    ("Shape", "Point", "聚合 0..*", False),
    ("Shape", "Connection", "关联 0..1", False),
    ("History", "Document", "依赖", True),
    ("Renderer", "Document", "依赖", True),
]


def uml_class_template() -> Document:
    return uml_from_spec(
        DEFAULT_UML_CLASSES,
        DEFAULT_UML_RELATIONS,
        title="UML 类图：图形编辑器核心模型",
        columns=4,
    )


def _uml_height(attributes: list[str], methods: list[str]) -> float:
    line_h = 22
    name_h = 42
    attr_h = max(30, len(attributes) * line_h + 14) if attributes else 30
    method_h = max(30, len(methods) * line_h + 14) if methods else 30
    return name_h + attr_h + method_h


def uml_from_spec(
    classes: list[tuple],
    relations: list[tuple] | None = None,
    *,
    title: str = "UML 类图",
    columns: int | None = None,
) -> Document:
    """根据类与关系数据自动网格布局 UML 类图。

    每个类为 ``(名称, 属性列表, 方法列表)``；关系为 ``(源, 目标, 标签, 是否虚线)``。
    """
    if not classes:
        raise ValueError("请至少提供一个类。")
    relations = relations or []

    count = len(classes)
    if columns is None:
        columns = max(1, min(4, math.ceil(math.sqrt(count))))
    rows = math.ceil(count / columns)

    col_w = 420
    col_gap = 60
    row_gap = 70
    left = 60
    top = 130

    heights = [_uml_height(attrs, methods) for _name, attrs, methods in classes]
    row_heights = [max(heights[r * columns:(r + 1) * columns] or [0]) for r in range(rows)]
    row_tops = [top + sum(row_heights[:r]) + r * row_gap for r in range(rows)]

    width = int(left * 2 + columns * col_w + (columns - 1) * col_gap)
    height = int(row_tops[-1] + row_heights[-1] + 120) if row_tops else 600

    doc = Document(width=max(width, 1200), height=max(height, 600))
    header = _node("text", doc.width / 2 - 340, 36, 680, 56, title, "#fff7d6", "#d1842f")
    doc.shapes.append(header)

    registry: dict[str, Shape] = {}
    for index, (name, attributes, methods) in enumerate(classes):
        col = index % columns
        row = index // columns
        x = left + col * (col_w + col_gap)
        y = row_tops[row]
        shape = _uml_class(doc, x=x, y=y, width=col_w, name=str(name), attributes=list(attributes), methods=list(methods))
        registry[str(name)] = shape

    for relation in relations:
        source = registry.get(str(relation[0]))
        target = registry.get(str(relation[1]))
        if not source or not target:
            continue
        label = relation[2] if len(relation) > 2 else ""
        dashed = bool(relation[3]) if len(relation) > 3 else False
        _uml_relation(doc, source, target, label, dashed=dashed)
    return doc


def parse_uml_text(text: str, *, title: str = "UML 类图") -> Document:
    """解析 UML 类图 DSL。

    示例::

        class Shape
          - id: str
          + move(dx, dy)
        class Style
          - fill: str
        Shape --> Style : 组合
        Renderer ..> Document : 依赖
    """
    classes: list[tuple[str, list[str], list[str]]] = []
    relations: list[tuple[str, str, str, bool]] = []
    index: dict[str, int] = {}
    current: int | None = None

    relation_re = re.compile(r"^(.+?)\s*(\.\.>|--?>|=>|->)\s*(.+?)\s*(?:[:：]\s*(.*))?$")

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lowered = line.lower()
        if lowered.startswith("class ") or lowered.startswith("类 "):
            name = line.split(None, 1)[1].strip()
            if name not in index:
                index[name] = len(classes)
                classes.append((name, [], []))
            current = index[name]
            continue
        if line[0] in "-•·":
            if current is not None:
                classes[current][1].append(line[1:].strip())
            continue
        if line[0] in "+*":
            if current is not None:
                classes[current][2].append(line[1:].strip())
            continue
        match = relation_re.match(line)
        if match and ("->" in line or ">" in line):
            source, arrow, target, label = match.group(1).strip(), match.group(2), match.group(3).strip(), (match.group(4) or "").strip()
            relations.append((source, target, label, arrow.startswith("..")))
            continue
        # 兜底：无标记的行视为当前类的属性
        if current is not None:
            classes[current][1].append(line)

    if not classes:
        raise ValueError("没有解析到类。示例：class Shape 然后用 - 列属性。")
    return uml_from_spec(classes, relations, title=title)


DEFAULT_GANTT_TASKS = [
    ("需求调研与方案", 0, 1, "#1d8a99"),
    ("数据结构与渲染框架", 1, 3, "#1d8a99"),
    ("基础图元与编辑", 2, 3, "#1d8a99"),
    ("流程图 / 电路图模板", 4, 2, "#d1842f"),
    ("三维图元与坐标标注", 5, 2, "#d1842f"),
    ("算法演示窗口", 6, 2, "#6c55ad"),
    ("文本生成流程图", 7, 1, "#6c55ad"),
    ("UML / 甘特 / 时序图", 7, 2, "#4d8a3f"),
    ("测试与答辩准备", 8, 2, "#c33f4a"),
]

DEFAULT_GANTT_MILESTONES = [("M1: 框架就绪", 4), ("M2: 模板完成", 7), ("M3: 答辩展示", 10)]

DEFAULT_GANTT_LEGEND = [
    ("基础与渲染", "#1d8a99"),
    ("应用模板", "#d1842f"),
    ("演示功能", "#6c55ad"),
    ("创新功能", "#4d8a3f"),
    ("收尾与答辩", "#c33f4a"),
]


def gantt_template() -> Document:
    return gantt_from_tasks(
        DEFAULT_GANTT_TASKS,
        milestones=DEFAULT_GANTT_MILESTONES,
        legend=DEFAULT_GANTT_LEGEND,
        title="甘特图：VectorCraft 项目进度",
    )


def gantt_from_tasks(
    tasks: list[tuple],
    *,
    milestones: list[tuple[str, int]] | None = None,
    legend: list[tuple[str, str]] | None = None,
    title: str = "甘特图",
) -> Document:
    """根据任务数据自动排版甘特图：周数、行数、网格、图例全部按数据算出。

    每个任务为 ``(名称, 起始周0基, 工期)`` 或 ``(名称, 起始周, 工期, 颜色)``。
    """
    if not tasks:
        raise ValueError("请至少提供一个任务。")
    milestones = milestones or []

    norm: list[tuple[str, int, int, str]] = []
    for index, task in enumerate(tasks):
        name, start_week, duration = task[0], int(task[1]), max(1, int(task[2]))
        color = task[3] if len(task) > 3 else DIAGRAM_PALETTE[index % len(DIAGRAM_PALETTE)]
        norm.append((str(name), max(0, start_week), duration, color))

    chart_left = 360
    chart_top = 150
    row_height = 56
    col_width = 110
    weeks = max(1, max(start + duration for _, start, duration, _ in norm))
    weeks = max(weeks, max((week for _, week in milestones), default=0))

    grid_right = chart_left + weeks * col_width
    grid_bottom = chart_top + len(norm) * row_height
    legend_rows = legend or []
    legend_y = grid_bottom + 110
    width = int(max(grid_right + 220, 80 + len(legend_rows) * 240 + 80, 1200))
    height = int((legend_y + 80) if legend_rows else (grid_bottom + 140))

    doc = Document(width=width, height=height)
    header = _node("text", width / 2 - 340, 32, 680, 56, title, "#fff7d6", "#d1842f")
    doc.shapes.append(header)

    head_label = _node("rect", 60, chart_top - 40, chart_left - 80, 36, "任务 / 周次", "#eef2f7", "#3a4355")
    head_label.style.font_size = 14
    doc.shapes.append(head_label)
    for week in range(weeks):
        x = chart_left + week * col_width
        cell = _node("rect", x, chart_top - 40, col_width, 36, f"第 {week + 1} 周", "#eef2f7", "#3a4355")
        cell.style.font_size = 13
        doc.shapes.append(cell)

    for index, (name, start_week, duration, color) in enumerate(norm):
        row_y = chart_top + index * row_height
        label = _node("rect", 60, row_y + 6, chart_left - 80, row_height - 12, name, "#ffffff", "#3a4355")
        label.style.font_size = 13
        doc.shapes.append(label)
        bar = _node(
            "round_rect",
            chart_left + start_week * col_width + 4,
            row_y + 12,
            duration * col_width - 8,
            row_height - 24,
            f"{duration} 周",
            color,
            color,
        )
        bar.style.font_size = 13
        bar.style.opacity = 0.92
        doc.shapes.append(bar)

    for week in range(weeks + 1):
        x = chart_left + week * col_width
        line = make_shape("line", x, chart_top - 4, 0, grid_bottom - chart_top + 8)
        line.points = [Point(x, chart_top - 4), Point(x, grid_bottom + 8)]
        line.style.stroke = "#cdd5e1"
        line.style.width = 1
        line.style.dash = "dotted" if week else "solid"
        doc.shapes.append(line)
    for row in range(len(norm) + 1):
        y = chart_top + row * row_height
        line = make_shape("line", 60, y, grid_right - 60, 0)
        line.points = [Point(60, y), Point(grid_right, y)]
        line.style.stroke = "#cdd5e1"
        line.style.width = 1
        doc.shapes.append(line)

    for name, week in milestones:
        x = chart_left + week * col_width - 18
        m = _node("diamond", x - 16, grid_bottom + 22, 40, 32, "", "#d1842f", "#d1842f")
        doc.shapes.append(m)
        text = _node("text", x - 70, grid_bottom + 56, 180, 28, name, "#ffffff", "#3a4355")
        text.style.font_size = 12
        text.style.width = 0
        doc.shapes.append(text)

    for index, (name, color) in enumerate(legend_rows):
        x = 80 + index * 240
        swatch = _node("rect", x, legend_y, 30, 22, "", color, color)
        doc.shapes.append(swatch)
        text = _node("text", x + 36, legend_y - 4, 200, 30, name, "#ffffff", "#3a4355")
        text.style.font_size = 13
        text.style.width = 0
        doc.shapes.append(text)

    return doc


def parse_gantt_text(text: str, *, title: str = "甘特图") -> Document:
    """解析甘特图大纲文本。

    支持的行格式::

        需求分析: 1-2          # 第 1 周到第 2 周（含两端）
        框架搭建: 2, 3         # 第 2 周开始，持续 3 周
        测试与答辩: 8 2        # 第 8 周开始，持续 2 周
        M1 框架就绪 @ 4        # 里程碑，落在第 4 周
    """
    tasks: list[tuple[str, int, int, str]] = []
    milestones: list[tuple[str, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "@" in line:
            name, _, week = line.partition("@")
            digits = re.findall(r"\d+", week)
            if digits:
                milestones.append((name.strip(" #-*").strip() or f"里程碑", int(digits[0])))
            continue
        if ":" in line or "：" in line:
            name, _, rest = line.replace("：", ":").partition(":")
        elif re.search(r"[,，]", line):
            name, _, rest = re.sub(r"，", ",", line).partition(",")
        else:
            parts = line.split()
            name, rest = parts[0], " ".join(parts[1:])
        rest = re.sub(r"[，]", ",", rest).strip()
        range_match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", rest)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            start0, duration = max(0, start - 1), max(1, end - start + 1)
        else:
            digits = re.findall(r"\d+", rest)
            if not digits:
                continue
            start0 = max(0, int(digits[0]) - 1)
            duration = max(1, int(digits[1])) if len(digits) > 1 else 1
        color = DIAGRAM_PALETTE[len(tasks) % len(DIAGRAM_PALETTE)]
        tasks.append((name.strip(" -*").strip(), start0, duration, color))
    if not tasks:
        raise ValueError("没有解析到任务。示例：需求分析: 1-2")
    return gantt_from_tasks(tasks, milestones=milestones, title=title)


DEFAULT_SEQUENCE_ACTORS = ["用户", "画布 Canvas", "Document", "Renderer", "Storage"]

DEFAULT_SEQUENCE_MESSAGES = [
    ("用户", "画布 Canvas", "点击「保存」按钮", "sync"),
    ("画布 Canvas", "Document", "to_dict()", "sync"),
    ("Document", "画布 Canvas", "返回字典数据", "return"),
    ("画布 Canvas", "Storage", "save_json(document, path)", "sync"),
    ("Storage", "Storage", "序列化 JSON 并写盘", "self"),
    ("Storage", "画布 Canvas", "保存成功", "return"),
    ("用户", "画布 Canvas", "点击「PNG」", "sync"),
    ("画布 Canvas", "Renderer", "render_document(document)", "sync"),
    ("Renderer", "Document", "遍历 shapes", "sync"),
    ("Document", "Renderer", "返回所有图元", "return"),
    ("Renderer", "画布 Canvas", "返回 PIL Image", "return"),
    ("画布 Canvas", "Storage", "image.save(path)", "sync"),
    ("Storage", "用户", "弹出「导出完成」提示", "return"),
]


def sequence_template() -> Document:
    return sequence_from_messages(
        DEFAULT_SEQUENCE_ACTORS,
        DEFAULT_SEQUENCE_MESSAGES,
        title="时序图：保存与导出流程",
    )


def sequence_from_messages(
    actors: list[str],
    messages: list[tuple],
    *,
    title: str = "时序图",
) -> Document:
    """根据生命线与消息列表自动排版时序图：消息 y 按顺序排，列位自动均分。

    每条消息为 ``(发起者, 接收者, 文字, 类型)``，类型取 ``sync`` / ``return`` / ``self``。
    """
    if not actors:
        raise ValueError("请至少提供一个参与者。")
    if not messages:
        raise ValueError("请至少提供一条消息。")

    margin = 220
    spacing = 320
    top = 140
    row_gap = 60
    start_y = top + 120

    actor_x = {name: margin + index * spacing for index, name in enumerate(actors)}
    width = int(margin * 2 + (len(actors) - 1) * spacing)
    lifeline_bottom = int(start_y + len(messages) * row_gap + 40)
    height = lifeline_bottom + 140

    doc = Document(width=max(width, 1200), height=height)
    header = _node("text", width / 2 - 340, 32, 680, 56, title, "#fff7d6", "#d1842f")
    doc.shapes.append(header)

    for name in actors:
        cx = actor_x[name]
        head = _node("round_rect", cx - 90, top, 180, 60, name, "#eef8fa", "#1d8a99")
        head.style.font_size = 16
        doc.shapes.append(head)
        line = make_shape("line", cx, top + 60, 0, lifeline_bottom - top - 60)
        line.points = [Point(cx, top + 60), Point(cx, lifeline_bottom)]
        line.style.stroke = "#7d8aa1"
        line.style.width = 1
        line.style.dash = "dashed"
        doc.shapes.append(line)

    for index, message in enumerate(messages):
        start_name, end_name, label, kind = message[0], message[1], message[2], (message[3] if len(message) > 3 else "sync")
        y = start_y + index * row_gap
        if start_name not in actor_x or end_name not in actor_x:
            continue
        start_x = actor_x[start_name]
        end_x = actor_x[end_name]
        if kind == "self":
            # self-call: small loop on the lifeline
            loop_w = 80
            mid_x = start_x
            line1 = make_shape("line", mid_x, y, loop_w, 0)
            line1.points = [Point(mid_x, y), Point(mid_x + loop_w, y)]
            line2 = make_shape("line", mid_x + loop_w, y, 0, 30)
            line2.points = [Point(mid_x + loop_w, y), Point(mid_x + loop_w, y + 30)]
            arrow = make_shape("arrow", mid_x + loop_w, y + 30, -loop_w, 0)
            arrow.points = [Point(mid_x + loop_w, y + 30), Point(mid_x, y + 30)]
            for shape in (line1, line2, arrow):
                shape.style.stroke = "#1d8a99"
                shape.style.width = 2
            doc.shapes.extend([line1, line2, arrow])
            text = _node("text", mid_x + loop_w + 8, y + 4, 220, 28, label, "#ffffff", "#3a4355")
            text.style.font_size = 13
            text.style.width = 0
            doc.shapes.append(text)
            continue

        if kind == "return":
            arrow = make_shape("line", start_x, y, end_x - start_x, 0)
            arrow.style.dash = "dashed"
        else:
            arrow = make_shape("arrow", start_x, y, end_x - start_x, 0)
        arrow.points = [Point(start_x, y), Point(end_x, y)]
        arrow.style.stroke = "#1d8a99" if kind != "return" else "#6c55ad"
        arrow.style.width = 2
        if kind == "return":
            # build a dashed arrowhead by adding a small arrow on top
            tip = make_shape("arrow", end_x - (16 if end_x > start_x else -16), y, 16 if end_x > start_x else -16, 0)
            tip.points = [Point(end_x - (16 if end_x > start_x else -16), y), Point(end_x, y)]
            tip.style.stroke = "#6c55ad"
            tip.style.width = 2
            doc.shapes.append(tip)
        doc.shapes.append(arrow)
        mid_x = (start_x + end_x) / 2
        text = _node("text", mid_x - 130, y - 32, 260, 30, label, "#ffffff", "#3a4355")
        text.style.font_size = 13
        text.style.width = 0
        doc.shapes.append(text)

    # footer note
    note = _node("round_rect", 160, lifeline_bottom + 20, max(600, doc.width - 320), 70, "时序图说明：实线箭头为同步调用，虚线箭头为返回，自身循环表示对象内部处理。", "#fff7d6", "#d1842f")
    note.style.font_size = 14
    doc.shapes.append(note)
    return doc


def parse_sequence_text(text: str, *, title: str = "时序图") -> Document:
    """解析时序图 DSL。

    示例::

        用户 -> 画布: 点击保存
        画布 -> Storage: save_json()
        Storage -> Storage: 写盘
        Storage --> 画布: 保存成功
    """
    actors: list[str] = []
    messages: list[tuple[str, str, str, str]] = []
    line_re = re.compile(r"^(.+?)\s*(-->|->|=>)\s*(.+?)\s*[:：]\s*(.*)$")

    def remember(name: str) -> None:
        if name not in actors:
            actors.append(name)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = line_re.match(line)
        if not match:
            continue
        source = match.group(1).strip()
        arrow = match.group(2)
        target = match.group(3).strip()
        label = match.group(4).strip()
        if not source or not target:
            continue
        remember(source)
        remember(target)
        if source == target:
            kind = "self"
        elif arrow.startswith("--"):
            kind = "return"
        else:
            kind = "sync"
        messages.append((source, target, label, kind))

    if not messages:
        raise ValueError("没有解析到消息。示例：用户 -> 画布: 点击保存")
    return sequence_from_messages(actors, messages, title=title)


def _uml_class(
    doc: Document,
    *,
    x: float,
    y: float,
    name: str,
    attributes: list[str],
    methods: list[str],
    width: float = 420,
) -> Shape:
    line_h = 22
    name_h = 42
    attr_h = max(30, len(attributes) * line_h + 14) if attributes else 30
    method_h = max(30, len(methods) * line_h + 14) if methods else 30
    total_h = name_h + attr_h + method_h

    # 外框 — 无文字
    container = _node("rect", x, y, width, total_h, "", "#f7fbff", "#3a4355")
    container.style.width = 2
    doc.shapes.append(container)

    # 类名色带
    band = _node("rect", x + 2, y + 2, width - 4, name_h - 3, name, "#1d8a99", "#1d8a99")
    band.style.font_size = 16
    band.style.stroke = "#ffffff"
    band.style.width = 0
    doc.shapes.append(band)

    # 分隔线 1（类名 / 属性）
    _uml_sep(doc, x, y + name_h, width)

    # 属性标签
    for index, attr in enumerate(attributes):
        lbl = _label(attr, x + 10, y + name_h + 7 + index * line_h, width - 20)
        lbl.style.font_size = 13
        doc.shapes.append(lbl)

    # 分隔线 2（属性 / 方法）
    _uml_sep(doc, x, y + name_h + attr_h, width)

    # 方法标签
    for index, method in enumerate(methods):
        lbl = _label(method, x + 10, y + name_h + attr_h + 7 + index * line_h, width - 20)
        lbl.style.font_size = 13
        doc.shapes.append(lbl)

    return container


def _uml_sep(doc: Document, x: float, y: float, width: float) -> None:
    line = make_shape("line", x, y, width, 0)
    line.points = [Point(x, y), Point(x + width, y)]
    line.style.stroke = "#8b97a8"
    line.style.width = 1
    doc.shapes.append(line)


def _uml_relation(doc: Document, source: Shape, target: Shape, label: str, *, dashed: bool = False) -> None:
    connector = make_shape("connector", 0, 0, 0, 0)
    connector.connection = Connection(source.id, target.id, "orthogonal")
    color = "#6c55ad" if dashed else "#3a4355"
    connector.style.stroke = color
    connector.style.width = 2
    if dashed:
        connector.style.dash = "dashed"
    doc.shapes.append(connector)
    if label:
        src = source.center()
        tgt = target.center()
        lbl_w = max(80, len(label) * 14 + 12)
        lbl = _label(label, (src.x + tgt.x) / 2 - lbl_w / 2, (src.y + tgt.y) / 2 - 14, lbl_w)
        lbl.style.font_size = 12
        lbl.style.stroke = color
        doc.shapes.append(lbl)


def _node(shape_type: str, x: float, y: float, w: float, h: float, text: str, fill: str, stroke: str) -> Shape:
    shape = make_shape(shape_type, x, y, w, h)
    shape.text = text
    shape.style.fill = fill
    shape.style.stroke = stroke
    shape.style.width = 2
    shape.style.font_size = 17 if shape_type != "text" else 20
    return shape


def _label(text: str, x: float, y: float, w: float = 72) -> Shape:
    label = make_shape("text", x, y, w, 34)
    label.text = text
    label.style.fill = "#ffffff"
    label.style.stroke = "#526072"
    label.style.width = 1
    label.style.font_size = 14
    return label


def _wire(points: list[tuple[float, float]], stroke: str) -> Shape:
    wire = make_shape("line", points[0][0], points[0][1], 0, 0)
    wire.points = [Point(x, y) for x, y in points]
    wire.style.stroke = stroke
    wire.style.width = 2
    wire.style.fill = "#ffffff"
    return wire


def _connect(doc: Document, start: Shape, end: Shape, style: str = "orthogonal") -> None:
    connector = make_shape("connector", 0, 0, 0, 0)
    connector.connection = Connection(start.id, end.id, style)
    connector.style.stroke = "#263346"
    connector.style.width = 2
    doc.shapes.append(connector)
