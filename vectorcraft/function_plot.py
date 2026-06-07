from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass

from .geometry import snap
from .model import Document, Point, Shape, make_shape


# 幂运算指数上限：超过即视为发散（同时挡掉 9**9**9 这类整数幂 DoS）。
MAX_EXP = 1024.0


SAFE_NAMES: dict[str, object] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "ln": math.log,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "fabs": math.fabs,
    "pow": math.pow,
    "min": min,
    "max": max,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "PI": math.pi,
    "E": math.e,
}


@dataclass
class PlotSpec:
    expression: str
    x_min: float = -10.0
    x_max: float = 10.0
    samples: int = 400
    color: str = "#1d8a99"
    line_width: int = 3


def _preprocess(expression: str) -> str:
    expr = expression.strip()
    if not expr:
        raise ValueError("请输入函数表达式。")
    expr = expr.replace("^", "**")
    expr = re.sub(r"\s+", "", expr)
    for prefix in ("y=", "Y=", "f(x)=", "F(x)="):
        if expr.startswith(prefix):
            expr = expr[len(prefix):]
            break
    # 先把科学计数法的指数标记 e/E 换成占位符，避免被下面的隐式乘号拆开
    # （否则 1e3 会变成 1*e3）。还原前的 § 不是字母/数字，不会触发隐式乘号。
    expr = re.sub(r"(\d)[eE]([+-]?\d)", r"\1§\2", expr)
    expr = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", expr)
    expr = re.sub(r"\)(\(|[a-zA-Z])", r")*\1", expr)
    expr = expr.replace("§", "e")
    return expr


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def _safe_pow(base: float, exponent: float) -> float:
    """以 float 求幂，指数过大/溢出/出现复数时返回 NaN——挡住 9**9**9 这类整数幂 DoS。"""
    try:
        if abs(exponent) > MAX_EXP:
            return float("nan")
        result = float(base) ** float(exponent)
    except (OverflowError, ValueError, ZeroDivisionError, ArithmeticError, TypeError):
        return float("nan")
    if isinstance(result, complex):
        return float("nan")
    return result


class _PowTransformer(ast.NodeTransformer):
    """把所有 ``a ** b`` 改写成 ``_safe_pow(a, b)``。"""

    def visit_BinOp(self, node: ast.BinOp):
        self.generic_visit(node)
        if isinstance(node.op, ast.Pow):
            return ast.Call(
                func=ast.Name(id="_safe_pow", ctx=ast.Load()),
                args=[node.left, node.right],
                keywords=[],
            )
        return node


def _validate(tree: ast.AST) -> None:
    """AST 白名单：只放行数值表达式，纵深防御 Attribute/Subscript/Lambda 等。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _ALLOWED_BINOPS):
                raise ValueError("表达式包含不支持的运算符。")
            continue
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _ALLOWED_UNARYOPS):
                raise ValueError("表达式包含不支持的运算符。")
            continue
        if isinstance(node, _ALLOWED_BINOPS + _ALLOWED_UNARYOPS):
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("表达式只允许数字常量。")
            continue
        if isinstance(node, ast.Name):
            if node.id not in SAFE_NAMES and node.id != "x":
                raise ValueError(f"表达式包含未授权的名称：{node.id}")
            continue
        if isinstance(node, ast.Call):
            if node.keywords or not isinstance(node.func, ast.Name) or node.func.id not in SAFE_NAMES:
                raise ValueError("只允许调用内置安全函数。")
            continue
        raise ValueError("表达式包含不被允许的语法。")


def _compile(expression: str):
    cleaned = _preprocess(expression)
    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"表达式无法解析：{exc.msg}") from exc
    _validate(tree)
    tree = _PowTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    code = compile(tree, "<plot>", "eval")
    return code, cleaned


def _make_evaluator(code):
    """返回单点求值闭包 f(x)->float|None，复用一个命名空间避免重复构建。"""
    env = dict(SAFE_NAMES)
    env["_safe_pow"] = _safe_pow
    sandbox = {"__builtins__": {}}

    def f(x: float) -> float | None:
        env["x"] = x
        try:
            value = eval(code, sandbox, env)
        except (ZeroDivisionError, ValueError, OverflowError, ArithmeticError):
            return None
        if isinstance(value, complex):
            return None
        try:
            y = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(y) or math.isinf(y):
            return None
        return y

    return f


def evaluate_samples(spec: PlotSpec) -> list[tuple[float, float | None]]:
    code, _cleaned = _compile(spec.expression)
    f = _make_evaluator(code)
    samples = max(20, min(4000, int(spec.samples)))
    if spec.x_max <= spec.x_min:
        raise ValueError("x 范围无效：x_max 必须大于 x_min。")
    span_x = spec.x_max - spec.x_min

    # 1) 均匀基础网格
    grid: list[tuple[float, float | None]] = [
        (spec.x_min + span_x * i / samples, f(spec.x_min + span_x * i / samples))
        for i in range(samples + 1)
    ]

    valid = [y for _, y in grid if y is not None]
    y_scale = max((max(valid) - min(valid)) if valid else 1.0, 1e-9)
    flat_tol = y_scale * 0.01
    budget = [8000]

    # 2) 自适应二分细化：中点偏离弦超过容差则继续细分（峰谷更平滑、定位间断）
    out: list[tuple[float, float | None]] = []
    for i in range(len(grid) - 1):
        x0, y0 = grid[i]
        x1, y1 = grid[i + 1]
        out.append((x0, y0))
        if budget[0] > 0:
            _refine(f, x0, y0, x1, y1, 0, flat_tol, out, budget)
    out.append(grid[-1])

    # 3) 渐近线检测：相邻有效点出现「符号翻转 + 大跳变」即判为间断，插入 None 断开
    return _break_discontinuities(out, y_scale)


def _refine(f, x0, y0, x1, y1, depth, tol, out, budget) -> None:
    if depth >= 6 or budget[0] <= 0:
        return
    xm = (x0 + x1) / 2
    ym = f(xm)
    defined = [v is not None for v in (y0, ym, y1)]
    if not any(defined):
        return
    if all(defined):
        need = abs(ym - (y0 + y1) / 2) > tol
    else:
        # 落在定义域边界附近，细分以更精确地定位断点
        need = True
    if need:
        _refine(f, x0, y0, xm, ym, depth + 1, tol, out, budget)
        out.append((xm, ym))
        budget[0] -= 1
        _refine(f, xm, ym, x1, y1, depth + 1, tol, out, budget)


def _break_discontinuities(points: list[tuple[float, float | None]], y_scale: float) -> list[tuple[float, float | None]]:
    diffs = [
        abs(b[1] - a[1])
        for a, b in zip(points, points[1:])
        if a[1] is not None and b[1] is not None
    ]
    if not diffs:
        return points
    median = sorted(diffs)[len(diffs) // 2]
    threshold = max(median * 60.0, y_scale * 0.5)
    result: list[tuple[float, float | None]] = []
    for index, (x, y) in enumerate(points):
        result.append((x, y))
        if index + 1 < len(points):
            x2, y2 = points[index + 1]
            if y is not None and y2 is not None and y * y2 < 0 and abs(y2 - y) > threshold:
                result.append(((x + x2) / 2, None))
    return result


def function_plot_document(specs: list[PlotSpec], *, title: str | None = None) -> Document:
    """Build a standalone document that plots one or more y=f(x) curves."""
    if not specs:
        raise ValueError("请至少提供一个函数表达式。")

    width = 1800
    height = 1100
    doc = Document(width=width, height=height)

    margin_left = 160
    margin_right = 80
    margin_top = 150
    margin_bottom = 130
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    x_min = min(spec.x_min for spec in specs)
    x_max = max(spec.x_max for spec in specs)

    sampled: list[tuple[PlotSpec, list[tuple[float, float | None]]]] = []
    all_y: list[float] = []
    for spec in specs:
        points = evaluate_samples(spec)
        sampled.append((spec, points))
        for _, y in points:
            if y is not None and abs(y) < 1e9:
                all_y.append(y)

    if all_y:
        y_min = min(all_y)
        y_max = max(all_y)
    else:
        y_min, y_max = -1.0, 1.0
    if abs(y_max - y_min) < 1e-6:
        y_max += 1.0
        y_min -= 1.0
    span = y_max - y_min
    y_min -= span * 0.08
    y_max += span * 0.08

    def to_screen(x: float, y: float) -> Point:
        sx = margin_left + (x - x_min) / (x_max - x_min) * plot_w
        sy = margin_top + (1 - (y - y_min) / (y_max - y_min)) * plot_h
        return Point(sx, sy)

    title_shape = make_shape("text", margin_left, 40, plot_w, 60)
    title_shape.text = title or "函数图像绘制"
    title_shape.style.fill = "#fff7d6"
    title_shape.style.stroke = "#d1842f"
    title_shape.style.font_size = 22
    doc.shapes.append(title_shape)

    # axis box (use a rectangle drawn from lines so we don't get fill that hides curves)
    frame_top = make_shape("line", margin_left, margin_top, plot_w, 0)
    frame_top.points = [Point(margin_left, margin_top), Point(margin_left + plot_w, margin_top)]
    frame_top.style.stroke = "#c2cad7"
    frame_top.style.width = 1
    frame_top.style.dash = "dashed"
    doc.shapes.append(frame_top)
    frame_right = make_shape("line", margin_left + plot_w, margin_top, 0, plot_h)
    frame_right.points = [Point(margin_left + plot_w, margin_top), Point(margin_left + plot_w, margin_top + plot_h)]
    frame_right.style.stroke = "#c2cad7"
    frame_right.style.width = 1
    frame_right.style.dash = "dashed"
    doc.shapes.append(frame_right)

    # grid lines
    grid_color = "#dbe2ec"
    x_ticks = _nice_ticks(x_min, x_max, 10)
    y_ticks = _nice_ticks(y_min, y_max, 8)
    for tick in x_ticks:
        sp = to_screen(tick, y_min)
        ep = to_screen(tick, y_max)
        line = make_shape("line", sp.x, sp.y, 0, plot_h)
        line.points = [Point(sp.x, margin_top), Point(sp.x, margin_top + plot_h)]
        line.style.stroke = grid_color
        line.style.width = 1
        line.style.dash = "dotted"
        doc.shapes.append(line)
    for tick in y_ticks:
        sp = to_screen(x_min, tick)
        ep = to_screen(x_max, tick)
        line = make_shape("line", sp.x, sp.y, plot_w, 0)
        line.points = [Point(margin_left, sp.y), Point(margin_left + plot_w, sp.y)]
        line.style.stroke = grid_color
        line.style.width = 1
        line.style.dash = "dotted"
        doc.shapes.append(line)

    # x axis (y=0) and y axis (x=0) if visible
    if y_min <= 0 <= y_max:
        zero = to_screen(x_min, 0)
        zero_end = to_screen(x_max, 0)
        axis = make_shape("arrow", zero.x, zero.y, plot_w, 0)
        axis.points = [Point(margin_left - 6, zero.y), Point(margin_left + plot_w + 6, zero.y)]
        axis.style.stroke = "#263346"
        axis.style.width = 2
        doc.shapes.append(axis)
    else:
        axis = make_shape("arrow", margin_left, margin_top + plot_h, plot_w, 0)
        axis.points = [Point(margin_left - 6, margin_top + plot_h), Point(margin_left + plot_w + 6, margin_top + plot_h)]
        axis.style.stroke = "#263346"
        axis.style.width = 2
        doc.shapes.append(axis)
    if x_min <= 0 <= x_max:
        zero = to_screen(0, y_min)
        zero_end = to_screen(0, y_max)
        axis = make_shape("arrow", zero.x, zero.y, 0, plot_h)
        axis.points = [Point(zero.x, margin_top + plot_h + 6), Point(zero.x, margin_top - 6)]
        axis.style.stroke = "#263346"
        axis.style.width = 2
        doc.shapes.append(axis)
    else:
        axis = make_shape("arrow", margin_left, margin_top, 0, plot_h)
        axis.points = [Point(margin_left, margin_top + plot_h + 6), Point(margin_left, margin_top - 6)]
        axis.style.stroke = "#263346"
        axis.style.width = 2
        doc.shapes.append(axis)

    # tick labels
    for tick in x_ticks:
        pos = to_screen(tick, y_min if not (y_min <= 0 <= y_max) else 0)
        label = make_shape("text", pos.x - 30, pos.y + 8, 60, 28)
        label.text = _format_tick(tick)
        label.style.fill = "#ffffff"
        label.style.stroke = "#3a4355"
        label.style.width = 0
        label.style.font_size = 12
        doc.shapes.append(label)
    for tick in y_ticks:
        pos = to_screen(x_min if not (x_min <= 0 <= x_max) else 0, tick)
        label = make_shape("text", pos.x - 60, pos.y - 14, 52, 28)
        label.text = _format_tick(tick)
        label.style.fill = "#ffffff"
        label.style.stroke = "#3a4355"
        label.style.width = 0
        label.style.font_size = 12
        doc.shapes.append(label)

    # axis labels
    xl = make_shape("text", margin_left + plot_w - 30, margin_top + plot_h + 30, 60, 30)
    xl.text = "x"
    xl.style.fill = "#ffffff"
    xl.style.stroke = "#1f2a44"
    xl.style.width = 0
    xl.style.font_size = 16
    doc.shapes.append(xl)
    yl = make_shape("text", margin_left - 50, margin_top - 30, 60, 30)
    yl.text = "y"
    yl.style.fill = "#ffffff"
    yl.style.stroke = "#1f2a44"
    yl.style.width = 0
    yl.style.font_size = 16
    doc.shapes.append(yl)

    # curves
    for index, (spec, points) in enumerate(sampled):
        segment: list[Point] = []
        last_valid = False
        for x, y in points:
            if y is None or y < y_min - span * 1.5 or y > y_max + span * 1.5:
                if len(segment) >= 2:
                    _append_curve(doc, segment, spec)
                segment = []
                last_valid = False
                continue
            segment.append(to_screen(x, y))
            last_valid = True
        if len(segment) >= 2:
            _append_curve(doc, segment, spec)

        legend = make_shape("text", margin_left + 14, margin_top + 14 + index * 34, 280, 28)
        legend.text = f"y = {spec.expression}"
        legend.style.fill = "#ffffff"
        legend.style.stroke = spec.color
        legend.style.width = 1
        legend.style.font_size = 14
        doc.shapes.append(legend)

    info = make_shape("text", margin_left, margin_top + plot_h + 56, plot_w, 36)
    info.text = f"采样数 {specs[0].samples}    x ∈ [{_format_tick(x_min)}, {_format_tick(x_max)}]    y ∈ [{_format_tick(y_min)}, {_format_tick(y_max)}]"
    info.style.fill = "#ffffff"
    info.style.stroke = "#526072"
    info.style.width = 1
    info.style.font_size = 13
    doc.shapes.append(info)

    return doc


def _append_curve(doc: Document, segment: list[Point], spec: PlotSpec) -> None:
    curve = make_shape("pen", segment[0].x, segment[0].y, 0, 0)
    curve.points = [Point(p.x, p.y) for p in segment]
    curve.style.stroke = spec.color
    curve.style.width = max(1, int(spec.line_width))
    curve.style.fill = "#ffffff"
    left = min(p.x for p in segment)
    top = min(p.y for p in segment)
    right = max(p.x for p in segment)
    bottom = max(p.y for p in segment)
    curve.x = left
    curve.y = top
    curve.w = max(1, right - left)
    curve.h = max(1, bottom - top)
    doc.shapes.append(curve)


def _nice_ticks(low: float, high: float, target: int) -> list[float]:
    if target <= 0 or high <= low:
        return []
    raw_step = (high - low) / target
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    candidates = [1, 2, 2.5, 5, 10]
    step = magnitude
    for option in candidates:
        if option * magnitude >= raw_step:
            step = option * magnitude
            break
    start = math.floor(low / step) * step
    ticks: list[float] = []
    value = start
    while value <= high + step * 0.5:
        if low - step * 0.5 <= value <= high + step * 0.5:
            ticks.append(round(value, 6))
        value += step
    return ticks


def _format_tick(value: float) -> str:
    if abs(value) < 1e-9:
        return "0"
    if abs(value) >= 1000 or abs(value) < 0.01:
        return f"{value:.2g}"
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")
