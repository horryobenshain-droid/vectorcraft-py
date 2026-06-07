from __future__ import annotations


ALGORITHMS = [
    "Bresenham 直线",
    "DDA 直线",
    "中点画圆",
    "扫描线填充",
    "Cohen-Sutherland 裁剪",
    "贝塞尔曲线采样",
]


ALGORITHM_INFO: dict[str, dict[str, object]] = {
    "Bresenham 直线": {
        "overview": "只使用整数误差项决定下一个像素，避免浮点运算，适合光栅设备上的直线绘制。",
        "steps": [
            "确定主方向轴，沿主方向逐像素推进。",
            "维护误差项 error，判断下一个像素是否需要在副方向上移动。",
            "每次更新 error，使像素尽量贴近理想直线。",
        ],
        "formula": "e2 = 2 * error；若 e2 >= dy 则 x 前进，若 e2 <= dx 则 y 前进。",
        "complexity": "时间复杂度 O(max(|dx|, |dy|))，空间复杂度 O(1)。",
        "usage": "底层线段绘制、网格线、矢量图导出前的像素化预览。",
    },
    "DDA 直线": {
        "overview": "Digital Differential Analyzer 通过等步长累加浮点坐标，再四舍五入到像素点。",
        "steps": [
            "计算 dx、dy，并取 steps = max(|dx|, |dy|)。",
            "令 x_inc = dx / steps，y_inc = dy / steps。",
            "每一步累加浮点坐标，再映射到最近的像素位置。",
        ],
        "formula": "x(k+1)=x(k)+dx/steps，y(k+1)=y(k)+dy/steps。",
        "complexity": "时间复杂度 O(steps)，实现直观，但依赖浮点累加。",
        "usage": "教学演示、快速原型、对比 Bresenham 整数误差法。",
    },
    "中点画圆": {
        "overview": "利用圆的八分对称性，只计算第一象限中的 1/8 圆弧，再镜像到其他象限。",
        "steps": [
            "从圆顶点 (0, r) 开始。",
            "使用判别式 d 判断下一个像素选择 E 还是 SE。",
            "每个计算点通过八分对称复制到整圆。",
        ],
        "formula": "d0 = 1 - r；若 d < 0 取 E，否则取 SE 并让 y 减 1。",
        "complexity": "时间复杂度 O(r)，只计算 1/8 圆弧，效率高。",
        "usage": "圆、圆角、节点端点、图标轮廓的光栅化绘制。",
    },
    "扫描线填充": {
        "overview": "按 y 方向逐行扫描多边形，计算扫描线与边的交点，成对填充交点之间的像素段。",
        "steps": [
            "找到多边形在当前扫描线上的所有边交点。",
            "按 x 坐标排序交点。",
            "每两个交点组成一个填充区间。",
        ],
        "formula": "x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)。",
        "complexity": "朴素实现约 O(H * E)，H 为扫描高度，E 为边数。",
        "usage": "多边形填充、流程图节点填色、矢量图形渲染。",
    },
    "Cohen-Sutherland 裁剪": {
        "overview": "为线段端点计算区域码，通过快速接受、快速拒绝和边界求交完成矩形窗口裁剪。",
        "steps": [
            "为端点计算上下左右四位区域码。",
            "两个区域码或运算为 0 时完全可见。",
            "两个区域码与运算非 0 时完全不可见。",
            "否则选择窗口外端点，与对应边界求交并更新端点。",
        ],
        "formula": "区域码：LEFT=1, RIGHT=2, BOTTOM=4, TOP=8。",
        "complexity": "单条线段通常只需少量迭代，适合矩形视窗裁剪。",
        "usage": "画布可视区裁剪、导出区域裁剪、窗口化显示。",
    },
    "贝塞尔曲线采样": {
        "overview": "用控制点定义曲线形状，通过参数 t 从 0 到 1 采样得到平滑曲线。",
        "steps": [
            "给出起点、终点和两个控制点。",
            "按 t 递增计算曲线点。",
            "连接采样点形成近似曲线。",
        ],
        "formula": "B(t)=(1-t)^3P0+3(1-t)^2tP1+3(1-t)t^2P2+t^3P3。",
        "complexity": "采样 n 个点时为 O(n)，采样越密曲线越平滑。",
        "usage": "曲线连接线、箭头路径、图形编辑器中的自由曲线。",
    },
}


def build_algorithm_frames(name: str) -> list[dict]:
    if name == "DDA 直线":
        return _dda_frames()
    if name == "中点画圆":
        return _midpoint_circle_frames()
    if name == "扫描线填充":
        return _scanline_frames()
    if name == "Cohen-Sutherland 裁剪":
        return _clip_frames()
    if name == "贝塞尔曲线采样":
        return _bezier_frames()
    return _bresenham_frames()


def algorithm_explanation(name: str, frame_detail: str = "", frame_index: int = 0, total: int = 0) -> str:
    info = ALGORITHM_INFO.get(name, ALGORITHM_INFO["Bresenham 直线"])
    steps = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(info["steps"]))
    progress = f"{frame_index + 1}/{total}" if total else "-"
    return (
        f"{name}\n\n"
        f"【核心思想】\n{info['overview']}\n\n"
        f"【当前帧】\n{progress}  {frame_detail or '观察算法状态变化。'}\n\n"
        f"【关键步骤】\n{steps}\n\n"
        f"【公式 / 判定】\n{info['formula']}\n\n"
        f"【复杂度】\n{info['complexity']}\n\n"
        f"【在本项目中的意义】\n{info['usage']}"
    )


def _base_items(title: str) -> list[dict]:
    return [
        {"type": "rect", "coords": (24, 24, 696, 436), "fill": "#ffffff", "outline": "#c7d1df", "width": 1},
        {"type": "text", "coords": (42, 42), "text": title, "fill": "#1d2433", "anchor": "nw", "font": ("Microsoft YaHei UI", 15, "bold")},
    ]


def _bresenham_points(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int, int]]:
    points: list[tuple[int, int, int]] = []
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    step = 0
    while True:
        points.append((x0, y0, err))
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
        if step > 1000:
            break
    return points


def _bresenham_frames() -> list[dict]:
    start = (82, 350)
    end = (628, 112)
    points = _bresenham_points(*start, *end)
    base = _base_items("Bresenham 直线绘制")
    base.extend(
        [
            {"type": "line", "coords": (*start, *end), "fill": "#b8c4d4", "width": 1, "dash": (6, 4)},
            {"type": "point", "coords": start, "size": 6, "fill": "#1d8a99"},
            {"type": "point", "coords": end, "size": 6, "fill": "#d1842f"},
        ]
    )

    frames: list[dict] = []
    for index in range(0, len(points), 6):
        visible = points[: index + 1]
        items = [*base]
        items.extend({"type": "point", "coords": (x, y), "size": 3, "fill": "#1d8a99"} for x, y, _err in visible)
        x, y, err = visible[-1]
        items.append({"type": "point", "coords": (x, y), "size": 7, "fill": "#d1842f"})
        detail = f"绘制到像素 ({x}, {y})，整数误差项 error={err}。"
        items.append(_bottom_text(f"step={index + 1}, pixel=({x}, {y}), error={err}"))
        frames.append({"caption": f"Bresenham 直线：第 {min(index + 1, len(points))}/{len(points)} 个像素", "detail": detail, "items": items})
    return frames


def _dda_frames() -> list[dict]:
    x0, y0 = 90, 342
    x1, y1 = 625, 118
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    x_inc = dx / steps
    y_inc = dy / steps
    samples: list[tuple[float, float, int, int]] = []
    x = float(x0)
    y = float(y0)
    for _ in range(steps + 1):
        samples.append((x, y, round(x), round(y)))
        x += x_inc
        y += y_inc

    base = _base_items("DDA 直线绘制")
    base.extend(
        [
            {"type": "line", "coords": (x0, y0, x1, y1), "fill": "#b8c4d4", "width": 1, "dash": (6, 4)},
            {"type": "text", "coords": (42, 78), "text": f"x_inc={x_inc:.3f}, y_inc={y_inc:.3f}", "fill": "#526072", "anchor": "nw", "font": ("Microsoft YaHei UI", 11)},
        ]
    )

    frames: list[dict] = []
    for index in range(0, len(samples), 10):
        visible = samples[: index + 1]
        items = [*base]
        items.extend({"type": "point", "coords": (rx, ry), "size": 3, "fill": "#1d8a99"} for _x, _y, rx, ry in visible)
        fx, fy, rx, ry = visible[-1]
        items.append({"type": "point", "coords": (rx, ry), "size": 7, "fill": "#d1842f"})
        detail = f"浮点坐标 ({fx:.2f}, {fy:.2f}) 被映射到像素 ({rx}, {ry})。"
        items.append(_bottom_text(f"float=({fx:.2f}, {fy:.2f}) -> pixel=({rx}, {ry})"))
        frames.append({"caption": f"DDA 直线：第 {min(index + 1, len(samples))}/{len(samples)} 次累加", "detail": detail, "items": items})
    return frames


def _circle_octant_points(cx: int, cy: int, x: int, y: int) -> list[tuple[int, int]]:
    return [
        (cx + x, cy + y),
        (cx - x, cy + y),
        (cx + x, cy - y),
        (cx - x, cy - y),
        (cx + y, cy + x),
        (cx - y, cy + x),
        (cx + y, cy - x),
        (cx - y, cy - x),
    ]


def _midpoint_circle_steps(cx: int, cy: int, radius: int) -> list[tuple[int, int, int, list[tuple[int, int]]]]:
    x = 0
    y = radius
    d = 1 - radius
    steps: list[tuple[int, int, int, list[tuple[int, int]]]] = []
    while x <= y:
        steps.append((x, y, d, _circle_octant_points(cx, cy, x, y)))
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1
    return steps


def _midpoint_circle_frames() -> list[dict]:
    cx, cy, radius = 360, 235, 135
    steps = _midpoint_circle_steps(cx, cy, radius)
    base = _base_items("中点画圆")
    base.extend(
        [
            {"type": "line", "coords": (cx - radius - 18, cy, cx + radius + 18, cy), "fill": "#d9e1ec", "width": 1, "dash": (4, 4)},
            {"type": "line", "coords": (cx, cy - radius - 18, cx, cy + radius + 18), "fill": "#d9e1ec", "width": 1, "dash": (4, 4)},
            {"type": "oval", "coords": (cx - radius, cy - radius, cx + radius, cy + radius), "fill": "", "outline": "#c7d1df", "width": 1},
            {"type": "point", "coords": (cx, cy), "size": 4, "fill": "#526072"},
        ]
    )

    frames: list[dict] = []
    for index in range(0, len(steps), 3):
        visible = steps[: index + 1]
        items = [*base]
        for _x, _y, _d, points in visible:
            for point in points:
                items.append({"type": "point", "coords": point, "size": 3, "fill": "#1d8a99"})
        x, y, d, points = visible[-1]
        for point in points:
            items.append({"type": "point", "coords": point, "size": 5, "fill": "#d1842f"})
        detail = f"只计算第一八分圆上的 ({x}, {y})，再通过对称得到 8 个圆周像素。判别式 d={d}。"
        items.append(_bottom_text(f"octant point=({x}, {y}), decision d={d}, symmetry points=8"))
        frames.append({"caption": f"中点画圆：第 {min(index + 1, len(steps))}/{len(steps)} 个八分圆点", "detail": detail, "items": items})
    return frames


def _scanline_frames() -> list[dict]:
    polygon = [(150, 120), (585, 92), (646, 255), (435, 370), (188, 320)]
    min_y = min(y for _x, y in polygon)
    max_y = max(y for _x, y in polygon)
    base = _base_items("多边形扫描线填充")
    base.append({"type": "polygon", "points": polygon, "fill": "", "outline": "#1d2433", "width": 2})

    spans: list[tuple[int, int, int]] = []
    for y in range(min_y, max_y + 1, 10):
        xs: list[float] = []
        for i, (x1, y1) in enumerate(polygon):
            x2, y2 = polygon[(i + 1) % len(polygon)]
            if (y1 <= y < y2) or (y2 <= y < y1):
                x = x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-9)
                xs.append(x)
        xs.sort()
        for i in range(0, len(xs), 2):
            if i + 1 < len(xs):
                spans.append((int(xs[i]), int(xs[i + 1]), y))

    frames: list[dict] = []
    for index in range(len(spans)):
        items = [*base]
        for x1, x2, y in spans[: index + 1]:
            items.append({"type": "line", "coords": (x1, y, x2, y), "fill": "#9dd7dd", "width": 8})
        items.append({"type": "polygon", "points": polygon, "fill": "", "outline": "#1d2433", "width": 2})
        x1, x2, y = spans[index]
        items.append({"type": "line", "coords": (42, y, 680, y), "fill": "#d1842f", "width": 1, "dash": (4, 4)})
        detail = f"当前扫描线 y={y}，交点成对后填充 x={x1} 到 x={x2}。"
        items.append(_bottom_text(f"scanline y={y}, fill span: {x1} -> {x2}"))
        frames.append({"caption": f"扫描线填充：第 {index + 1}/{len(spans)} 条填充段", "detail": detail, "items": items})
    return frames


def _clip_frames() -> list[dict]:
    rect = (190, 120, 545, 330)
    line = (70, 76, 660, 388)
    clipped = (190, 139, 545, 326)
    frames: list[dict] = []
    captions = [
        ("原始线段跨越裁剪窗口，端点区域码分别位于窗口外部。", "计算两个端点的区域码，判断是否完全可见或完全不可见。"),
        ("左上端点在窗口左侧，先与左边界求交。", "替换窗口外端点，使线段逐步靠近可见区域。"),
        ("右下端点在窗口右侧和下方，继续与右边界求交。", "继续选择窗口外端点，并根据区域码定位求交边界。"),
        ("两个端点都进入窗口，保留裁剪后的可见线段。", "区域码或运算为 0，说明裁剪完成。"),
    ]
    for index, (caption, detail) in enumerate(captions):
        items = _base_items("Cohen-Sutherland 线段裁剪")
        items.append({"type": "rect", "coords": rect, "fill": "", "outline": "#1d8a99", "width": 3})
        items.append({"type": "text", "coords": (202, 96), "text": "裁剪窗口", "fill": "#1d8a99", "anchor": "nw", "font": ("Microsoft YaHei UI", 11)})
        if index == 0:
            items.append({"type": "line", "coords": line, "fill": "#d1842f", "width": 4})
        elif index == 1:
            items.append({"type": "line", "coords": line, "fill": "#c7d1df", "width": 3, "dash": (6, 4)})
            items.append({"type": "point", "coords": (190, 139), "size": 7, "fill": "#d1842f"})
            items.append({"type": "line", "coords": (190, 139, 660, 388), "fill": "#d1842f", "width": 4})
        elif index == 2:
            items.append({"type": "line", "coords": line, "fill": "#c7d1df", "width": 3, "dash": (6, 4)})
            items.append({"type": "point", "coords": (545, 326), "size": 7, "fill": "#d1842f"})
            items.append({"type": "line", "coords": clipped, "fill": "#d1842f", "width": 4})
        else:
            items.append({"type": "line", "coords": line, "fill": "#c7d1df", "width": 2, "dash": (6, 4)})
            items.append({"type": "line", "coords": clipped, "fill": "#1d8a99", "width": 5})
        items.append(_bottom_text(caption))
        frames.append({"caption": f"Cohen-Sutherland 裁剪：步骤 {index + 1}/4", "detail": detail, "items": items})
    return frames


def _bezier_point(points: list[tuple[float, float]], t: float) -> tuple[float, float]:
    working = points[:]
    while len(working) > 1:
        working = [
            (working[i][0] * (1 - t) + working[i + 1][0] * t, working[i][1] * (1 - t) + working[i + 1][1] * t)
            for i in range(len(working) - 1)
        ]
    return working[0]


def _bezier_frames() -> list[dict]:
    controls = [(90, 330), (220, 70), (520, 92), (640, 330)]
    samples = [_bezier_point(controls, i / 60) for i in range(61)]
    base = _base_items("三次贝塞尔曲线采样")
    base.append({"type": "line", "coords": (*controls[0], *controls[1]), "fill": "#c7d1df", "width": 1, "dash": (5, 4)})
    base.append({"type": "line", "coords": (*controls[1], *controls[2]), "fill": "#c7d1df", "width": 1, "dash": (5, 4)})
    base.append({"type": "line", "coords": (*controls[2], *controls[3]), "fill": "#c7d1df", "width": 1, "dash": (5, 4)})
    for point in controls:
        base.append({"type": "point", "coords": point, "size": 6, "fill": "#d1842f"})

    frames: list[dict] = []
    for index in range(0, len(samples), 2):
        items = [*base]
        for start, end in zip(samples[:index], samples[1 : index + 1]):
            items.append({"type": "line", "coords": (*start, *end), "fill": "#1d8a99", "width": 3})
        current = samples[index]
        items.append({"type": "point", "coords": current, "size": 7, "fill": "#1d8a99"})
        detail = f"当前参数 t={index / 60:.2f}，采样点约为 ({current[0]:.1f}, {current[1]:.1f})。"
        items.append(_bottom_text(f"t={index / 60:.2f}, point=({current[0]:.1f}, {current[1]:.1f})"))
        frames.append({"caption": f"贝塞尔曲线采样：t={index / 60:.2f}", "detail": detail, "items": items})
    return frames


def _bottom_text(text: str) -> dict:
    return {
        "type": "text",
        "coords": (42, 394),
        "text": text,
        "fill": "#526072",
        "anchor": "nw",
        "font": ("Microsoft YaHei UI", 11),
    }
