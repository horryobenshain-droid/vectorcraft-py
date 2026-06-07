from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from collections.abc import Callable
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk

from . import APP_NAME
from .algorithm_steps import ALGORITHMS, algorithm_explanation, build_algorithm_frames
from .auto_flow import generate_flowchart_from_text
from .function_plot import PlotSpec, function_plot_document
from .geometry import Point, cohen_sutherland_clip, rect_intersects_shape, shape_hit, snap
from .history import History
from .mind_map import generate_mind_map_from_text
from .model import DEFAULT_LABELS, Connection, Document, Shape, make_shape
from .online_assets import AssetResult, download_asset, load_thumbnail, placeholder_thumbnail, search_assets
from .renderer import Renderer
from .shape_recognizer import recognize_stroke, shape_from_recognition
from .storage import export_png, export_svg, load_json, load_workspace, save_json, save_workspace
from .templates import (
    circuit_template,
    flowchart_template,
    gantt_template,
    org_template,
    parse_gantt_text,
    parse_sequence_text,
    parse_uml_text,
    sequence_template,
    uml_class_template,
)


TOOL_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("工具", [("select", "选择"), ("pan", "视图"), ("connector", "连接"), ("text", "文本"), ("pen", "画笔")]),
    ("基础", [("rect", "矩形"), ("round_rect", "圆角"), ("ellipse", "椭圆"), ("diamond", "菱形"), ("triangle", "三角"), ("line", "直线"), ("arrow", "箭头")]),
    ("三维", [("cube", "正方体"), ("cuboid", "长方体"), ("sphere", "球体"), ("coord3d", "坐标系")]),
    ("流程", [("terminator", "开始"), ("process", "处理"), ("decision", "判断"), ("io", "输入"), ("database", "数据"), ("document", "文档")]),
    ("电路", [("resistor", "电阻"), ("capacitor", "电容"), ("battery", "电池"), ("switch", "开关"), ("ground", "接地"), ("led", "LED")]),
]

# 淡蓝紫主题 —— 简约大气
THEME = {
    "app_bg": "#f1f2fb",       # 应用窗口底色（淡薰衣草灰）
    "panel": "#ffffff",        # 侧栏 / 属性面板
    "ribbon": "#f6f6fd",       # 顶部功能区
    "stage": "#e7e8f6",        # 画布舞台区
    "viewport": "#ececf8",     # 渲染视口底色
    "topbar": "#3b3a6b",       # 顶栏深靛
    "topbar_btn": "#4c4a85",   # 顶栏按钮
    "accent": "#6c6fd4",       # 主强调色（蓝紫）
    "accent_dark": "#565ac0",  # 按下
    "accent_soft": "#ececfb",  # 悬停浅底
    "accent_tint": "#e1e2f7",  # 选中浅底
    "text": "#2d2f4d",         # 主文字
    "subtext": "#6b6e8d",      # 次要文字
    "border": "#dcdcf0",       # 边框
    "tool_bg": "#f4f5fc",      # 工具按钮默认底
    "tool_text": "#3a3d5c",    # 工具按钮文字
}

# 取色板：以柔和的蓝紫填充为主，并保留几个强调色调。
PALETTE = ["#ffffff", "#f3f4fd", "#eceefb", "#e6e8fb", "#eef2ff", "#f1ecfb", "#fdeef6", "#6c6fd4", "#8a78d6", "#3b3a6b"]


class VectorCraftApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1280x820")
        self.root.minsize(980, 640)
        self.root.configure(bg=THEME["app_bg"])
        self._configure_style()

        self.document = Document()
        self.renderer = Renderer()
        self.history = History()
        self.current_path: Path | None = None
        self.pages: list[dict] = [{"name": "页面 1", "document": self.document, "history": self.history}]
        self.current_page_index = 0
        self._page_window: tk.Toplevel | None = None
        self._page_listbox: tk.Listbox | None = None
        self.auto_recognize_var = tk.BooleanVar(value=False)

        self.zoom = 0.82
        self.offset = Point(95, 56)
        self.tool = "select"
        self.selected_ids: set[str] = set()
        self.clipboard: list[Shape] = []
        self.preview_shape: Shape | None = None
        self.connector_start_id: str | None = None

        self.drag_start_screen: Point | None = None
        self.drag_start_world: Point | None = None
        self.last_drag_world: Point | None = None
        self.resize_start_bounds: dict[str, tuple[float, float, float, float]] = {}
        self.resize_handle = ""
        self.drag_mode = ""
        self.marquee: tuple[Point, Point] | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._image_id: int | None = None
        self._redraw_after_id: str | None = None
        self.tool_buttons: dict[str, tk.Button] = {}
        self.replay_frames: list[dict] = []
        self.max_replay_frames = 90
        self._replay_after_id: str | None = None
        self._replay_canvas: tk.Canvas | None = None
        self._replay_image_id: int | None = None
        self._replay_photo: ImageTk.PhotoImage | None = None
        self._replay_status_var: tk.StringVar | None = None
        self._replay_scale: ttk.Scale | None = None
        self._replay_index = 0
        self._replay_playing = False
        self._syncing_replay_scale = False
        self._algorithm_after_id: str | None = None
        self._algorithm_canvas: tk.Canvas | None = None
        self._algorithm_frames: list[dict] = []
        self._algorithm_index = 0
        self._algorithm_playing = False
        self._algorithm_status_var: tk.StringVar | None = None
        self._algorithm_choice_var: tk.StringVar | None = None
        self._algorithm_info_text: tk.Text | None = None
        self._asset_window: tk.Toplevel | None = None
        self._asset_result_photos: list[ImageTk.PhotoImage] = []
        self._asset_search_token = 0
        self._toolbar_panel: ttk.Frame | None = None
        self._toolbar_toggle_button: ttk.Button | None = None
        self._toolbar_panel_visible = True

        self.show_grid_var = tk.BooleanVar(value=True)
        self.snap_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")
        self.cursor_var = tk.StringVar(value="x: 0, y: 0")
        self.selection_var = tk.StringVar(value="未选择")

        self.prop_vars = {
            "x": tk.StringVar(),
            "y": tk.StringVar(),
            "w": tk.StringVar(),
            "h": tk.StringVar(),
            "rotation": tk.StringVar(),
            "line_width": tk.StringVar(value="2"),
            "text": tk.StringVar(),
            "fill": tk.StringVar(value="#f7fbff"),
            "stroke": tk.StringVar(value="#1f2a44"),
            "dash": tk.StringVar(value="solid"),
            "connector": tk.StringVar(value="orthogonal"),
        }

        self._build_ui()
        self._bind_events()
        self.load_template("flow", record=False)

    def run(self) -> None:
        self.root.mainloop()

    def _configure_style(self) -> None:
        t = THEME
        font = "Microsoft YaHei UI"
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(".", font=(font, 10), background=t["app_bg"], foreground=t["text"])

        # 容器
        self.style.configure("Topbar.TFrame", background=t["topbar"])
        self.style.configure("Ribbon.TFrame", background=t["ribbon"])
        self.style.configure("ToolbarPanel.TFrame", background=t["ribbon"])
        self.style.configure("ToolbarGroup.TFrame", background=t["ribbon"])
        self.style.configure("Side.TFrame", background=t["panel"])
        self.style.configure("Stage.TFrame", background=t["stage"])
        self.style.configure("Status.TFrame", background=t["ribbon"])

        # 标题与文字
        self.style.configure("Brand.TLabel", background=t["topbar"], foreground="#ffffff", font=(font, 15, "bold"))
        self.style.configure("ToolbarTitle.TLabel", background=t["ribbon"], foreground=t["text"], font=(font, 10, "bold"))
        self.style.configure("ToolbarMetric.TLabel", background=t["ribbon"], foreground=t["subtext"])
        self.style.configure("Section.TLabel", background=t["panel"], foreground=t["subtext"], font=(font, 10, "bold"))
        self.style.configure("Panel.TLabel", background=t["panel"], foreground=t["subtext"])
        self.style.configure("Metric.TLabel", background=t["panel"], foreground=t["subtext"])

        # 顶栏按钮
        self.style.configure("Topbar.TButton", background=t["topbar_btn"], foreground="#f5f6ff", borderwidth=0, focusthickness=0, padding=(13, 7))
        self.style.map("Topbar.TButton", background=[("active", t["accent"]), ("pressed", t["accent_dark"])], foreground=[("active", "#ffffff")])

        # 功能区按钮（扁平、淡蓝紫悬停）
        self.style.configure("Ribbon.TButton", background=t["panel"], foreground=t["tool_text"], bordercolor=t["border"], borderwidth=1, focusthickness=0, padding=(10, 6))
        self.style.map(
            "Ribbon.TButton",
            background=[("active", t["accent_soft"]), ("pressed", t["accent_tint"])],
            bordercolor=[("active", t["accent"]), ("pressed", t["accent"])],
            foreground=[("active", t["accent"]), ("pressed", t["accent_dark"])],
        )

        # 普通 ttk 按钮（对话框、属性面板等）
        self.style.configure("TButton", background=t["panel"], foreground=t["tool_text"], bordercolor=t["border"], borderwidth=1, focusthickness=0, padding=(8, 5))
        self.style.map(
            "TButton",
            background=[("active", t["accent_soft"]), ("pressed", t["accent_tint"])],
            bordercolor=[("active", t["accent"]), ("pressed", t["accent"])],
            foreground=[("active", t["accent"]), ("pressed", t["accent_dark"])],
        )

        # 顶部功能区选项卡
        self.style.configure("TNotebook", background=t["ribbon"], borderwidth=0, tabmargins=(8, 6, 8, 0))
        self.style.configure("TNotebook.Tab", background=t["ribbon"], foreground=t["subtext"], borderwidth=0, padding=(18, 8), font=(font, 10))
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", t["panel"]), ("active", t["accent_soft"])],
            foreground=[("selected", t["accent"]), ("active", t["text"])],
        )

        # 勾选框 / 输入控件
        self.style.configure("TCheckbutton", background=t["ribbon"], foreground=t["text"])
        self.style.map("TCheckbutton", foreground=[("active", t["accent"])])
        self.style.configure("TEntry", fieldbackground="#ffffff", bordercolor=t["border"], lightcolor=t["accent"], insertcolor=t["accent"], padding=(6, 5))
        self.style.map("TEntry", bordercolor=[("focus", t["accent"])])
        self.style.configure("TCombobox", fieldbackground="#ffffff", background=t["panel"], bordercolor=t["border"], arrowcolor=t["accent"], padding=(6, 5))
        self.style.map("TCombobox", bordercolor=[("focus", t["accent"])])

        # 滚动条与滑块
        self.style.configure("TScrollbar", background=t["accent_tint"], troughcolor=t["app_bg"], bordercolor=t["app_bg"], arrowcolor=t["accent"])
        self.style.configure("TScale", background=t["app_bg"], troughcolor=t["accent_tint"])

    def _build_ui(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(self.root, padding=(12, 8), style="Topbar.TFrame")
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        toolbar.columnconfigure(2, weight=1)
        ttk.Label(toolbar, text="VectorCraft-Py", style="Brand.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 18))
        self._toolbar_toggle_button = ttk.Button(
            toolbar,
            text="收起工具栏",
            command=self.toggle_toolbar_panel,
            style="Topbar.TButton",
        )
        self._toolbar_toggle_button.grid(row=0, column=1, sticky="w")

        self._toolbar_panel = self._build_toolbar_panel()
        self._toolbar_panel_visible = True

        left = ttk.Frame(self.root, padding=10, style="Side.TFrame")
        left.grid(row=2, column=0, sticky="ns")
        for group_name, tools in TOOL_GROUPS:
            ttk.Label(left, text=group_name, style="Section.TLabel").pack(anchor="w", pady=(8, 5))
            grid = ttk.Frame(left, style="Side.TFrame")
            grid.pack(anchor="w")
            for index, (tool, label) in enumerate(tools):
                button = tk.Button(
                    grid,
                    text=label,
                    width=6,
                    height=1,
                    command=lambda t=tool: self.set_tool(t),
                    bg=THEME["tool_bg"],
                    fg=THEME["tool_text"],
                    activebackground=THEME["accent_soft"],
                    activeforeground=THEME["accent"],
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    font=("Microsoft YaHei UI", 9),
                    padx=4,
                    pady=5,
                )
                button.grid(row=index // 2, column=index % 2, padx=3, pady=3)
                self.tool_buttons[tool] = button

        stage = ttk.Frame(self.root, style="Stage.TFrame")
        stage.grid(row=2, column=1, sticky="nsew")
        stage.columnconfigure(0, weight=1)
        stage.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(stage, bg=THEME["viewport"], highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        inspector = ttk.Frame(self.root, padding=12, style="Side.TFrame")
        inspector.grid(row=2, column=2, sticky="ns")
        self._build_inspector(inspector)

        status = ttk.Frame(self.root, padding=(12, 5), style="Status.TFrame")
        status.grid(row=3, column=0, columnspan=3, sticky="ew")
        ttk.Label(status, textvariable=self.status_var).pack(side="left")
        ttk.Label(status, textvariable=self.cursor_var).pack(side="right")
        self.refresh_tool_buttons()

    def _build_toolbar_panel(self) -> ttk.Frame:
        panel = ttk.Frame(self.root, padding=(4, 0), style="ToolbarPanel.TFrame")
        panel.grid(row=1, column=0, columnspan=3, sticky="ew")
        panel.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(panel)
        notebook.pack(fill="x", expand=True)

        # --- 文件 & 编辑 ---
        tab_file = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_file, text=" 文件 ")
        for col in range(10):
            tab_file.columnconfigure(col, weight=1)
        file_buttons = [
            ("新建", self.new_document), ("打开", self.open_document), ("保存", self.save_document),
            ("PNG", self.export_png), ("SVG", self.export_svg),
            ("撤销", self.undo), ("重做", self.redo),
            ("复制", self.copy_selected), ("粘贴", self.paste_clipboard), ("删除", self.delete_selected),
        ]
        for index, (text, command) in enumerate(file_buttons):
            ttk.Button(tab_file, text=text, command=command, style="Ribbon.TButton", width=7).grid(
                row=0, column=index, sticky="ew", padx=2, pady=2)

        # --- 图形 & 变换 ---
        tab_edit = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_edit, text=" 变换 ")
        for col in range(8):
            tab_edit.columnconfigure(col, weight=1)
        edit_buttons = [
            ("水平镜像", lambda: self.mirror_selected("x")),
            ("垂直镜像", lambda: self.mirror_selected("y")),
            ("裁剪", self.clip_lines_to_rect),
            ("置顶", self.bring_front),
            ("置底", self.send_back),
        ]
        for index, (text, command) in enumerate(edit_buttons):
            ttk.Button(tab_edit, text=text, command=command, style="Ribbon.TButton", width=8).grid(
                row=0, column=index, sticky="ew", padx=2, pady=2)

        # --- 模板 ---
        tab_tpl = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_tpl, text=" 模板 ")
        for col in range(6):
            tab_tpl.columnconfigure(col, weight=1)
        tpl_buttons = [
            ("流程图", lambda: self.load_template("flow")),
            ("组织结构图", lambda: self.load_template("org")),
            ("电路图", lambda: self.load_template("circuit")),
            ("UML 类图", lambda: self.load_template("uml")),
            ("甘特图", lambda: self.load_template("gantt")),
            ("时序图", lambda: self.load_template("sequence")),
        ]
        for index, (text, command) in enumerate(tpl_buttons):
            ttk.Button(tab_tpl, text=text, command=command, style="Ribbon.TButton", width=10).grid(
                row=0, column=index, sticky="ew", padx=2, pady=2)

        # --- 生成 ---
        tab_gen = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_gen, text=" 智能生成 ")
        for col in range(5):
            tab_gen.columnconfigure(col, weight=1)
        gen_buttons = [
            ("文本生成流程图", self.open_text_flow_dialog),
            ("思维导图", self.open_mind_map_dialog),
            ("函数图像", self.open_function_plot_dialog),
            ("图表生成", self.open_diagram_dialog),
            ("在线图库", self.open_asset_search_window),
        ]
        for index, (text, command) in enumerate(gen_buttons):
            ttk.Button(tab_gen, text=text, command=command, style="Ribbon.TButton", width=12).grid(
                row=0, column=index, sticky="ew", padx=2, pady=2)

        # --- 演示 ---
        tab_demo = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_demo, text=" 演示 ")
        for col in range(3):
            tab_demo.columnconfigure(col, weight=1)
        demo_buttons = [
            ("算法演示", self.open_algorithm_demo),
            ("操作回放", self.open_replay_window),
        ]
        for index, (text, command) in enumerate(demo_buttons):
            ttk.Button(tab_demo, text=text, command=command, style="Ribbon.TButton", width=10).grid(
                row=0, column=index, sticky="ew", padx=2, pady=2)

        # --- 视图 & 页面 ---
        tab_view = ttk.Frame(notebook, padding=6, style="Ribbon.TFrame")
        notebook.add(tab_view, text=" 视图 & 页面 ")
        for col in range(10):
            tab_view.columnconfigure(col, weight=1)
        ttk.Checkbutton(tab_view, text="网格", variable=self.show_grid_var, command=self.redraw).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(tab_view, text="吸附", variable=self.snap_var).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(tab_view, text="智能识别", variable=self.auto_recognize_var).grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Label(tab_view, text="画笔", style="ToolbarMetric.TLabel").grid(row=0, column=3, sticky="e", padx=(6, 2), pady=2)
        pen_width = tk.Spinbox(tab_view, from_=1, to=24, increment=1, width=4, textvariable=self.prop_vars["line_width"], command=self.apply_properties)
        pen_width.grid(row=0, column=4, sticky="w", padx=2, pady=2)
        pen_width.bind("<Return>", lambda _event: self.apply_properties())
        pen_width.bind("<FocusOut>", lambda _event: self.apply_properties())
        ttk.Button(tab_view, text="画笔颜色", command=lambda: self.pick_color("stroke"), style="Ribbon.TButton").grid(row=0, column=5, sticky="ew", padx=2, pady=2)
        ttk.Button(tab_view, text="缩小", command=lambda: self.change_zoom(1 / 1.12), style="Ribbon.TButton").grid(row=0, column=6, sticky="ew", padx=2, pady=2)
        ttk.Button(tab_view, text="放大", command=lambda: self.change_zoom(1.12), style="Ribbon.TButton").grid(row=0, column=7, sticky="ew", padx=2, pady=2)
        ttk.Button(tab_view, text="新页面", command=self.add_page, style="Ribbon.TButton").grid(row=0, column=8, sticky="ew", padx=2, pady=2)
        ttk.Button(tab_view, text="页面管理", command=self.open_pages_window, style="Ribbon.TButton").grid(row=0, column=9, sticky="ew", padx=2, pady=2)
        return panel

    def _build_toolbar_button_group(
        self,
        parent: ttk.Frame,
        title: str,
        actions: list[tuple[str, Callable[[], None]]],
        row: int,
        column: int,
        columns: int,
    ) -> None:
        group = ttk.Frame(parent, padding=(4, 6), style="ToolbarGroup.TFrame")
        group.grid(row=row, column=column, sticky="new", padx=8, pady=(0 if row == 0 else 8, 0))
        for group_column in range(columns):
            group.columnconfigure(group_column, weight=1)
        ttk.Label(group, text=title, style="ToolbarTitle.TLabel").grid(row=0, column=0, columnspan=columns, sticky="w", padx=2, pady=(0, 4))
        for index, (text, command) in enumerate(actions):
            ttk.Button(group, text=text, command=command, style="Ribbon.TButton", width=8).grid(
                row=1 + index // columns,
                column=index % columns,
                sticky="ew",
                padx=2,
                pady=2,
            )

    def toggle_toolbar_panel(self) -> None:
        if self._toolbar_panel_visible:
            self._toolbar_panel_visible = False
            if self._toolbar_panel:
                self._toolbar_panel.grid_remove()
            if self._toolbar_toggle_button:
                self._toolbar_toggle_button.configure(text="显示工具栏")
        else:
            self._toolbar_panel_visible = True
            if self._toolbar_panel:
                self._toolbar_panel.grid()
            if self._toolbar_toggle_button:
                self._toolbar_toggle_button.configure(text="收起工具栏")
        self.request_redraw()

    def _build_inspector(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="属性", font=("", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(parent, textvariable=self.selection_var, width=28).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        fields = [("x", "X"), ("y", "Y"), ("w", "宽"), ("h", "高"), ("rotation", "角度"), ("line_width", "线宽")]
        for index, (key, label) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=2 + index, column=0, sticky="w", pady=3)
            entry = ttk.Entry(parent, textvariable=self.prop_vars[key], width=16)
            entry.grid(row=2 + index, column=1, sticky="ew", pady=3)
            entry.bind("<Return>", lambda _event: self.apply_properties())
            entry.bind("<FocusOut>", lambda _event: self.apply_properties())

        row = 2 + len(fields)
        ttk.Label(parent, text="文本").grid(row=row, column=0, sticky="w", pady=3)
        text_entry = ttk.Entry(parent, textvariable=self.prop_vars["text"], width=18)
        text_entry.grid(row=row, column=1, sticky="ew", pady=3)
        text_entry.bind("<Return>", lambda _event: self.apply_properties())
        text_entry.bind("<FocusOut>", lambda _event: self.apply_properties())

        row += 1
        ttk.Button(parent, text="填充色", command=lambda: self.pick_color("fill")).grid(row=row, column=0, sticky="ew", pady=3)
        ttk.Button(parent, text="描边色", command=lambda: self.pick_color("stroke")).grid(row=row, column=1, sticky="ew", pady=3)
        row += 1
        swatch_frame = ttk.Frame(parent)
        swatch_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4)
        for i, color in enumerate(PALETTE):
            btn = tk.Button(swatch_frame, bg=color, width=2, command=lambda c=color: self.apply_swatch(c))
            btn.grid(row=i // 5, column=i % 5, padx=2, pady=2)

        row += 1
        ttk.Label(parent, text="线型").grid(row=row, column=0, sticky="w", pady=3)
        dash = ttk.Combobox(parent, textvariable=self.prop_vars["dash"], values=["solid", "dashed", "dotted"], width=14, state="readonly")
        dash.grid(row=row, column=1, sticky="ew", pady=3)
        dash.bind("<<ComboboxSelected>>", lambda _event: self.apply_properties())

        row += 1
        ttk.Label(parent, text="连接").grid(row=row, column=0, sticky="w", pady=3)
        connector = ttk.Combobox(parent, textvariable=self.prop_vars["connector"], values=["orthogonal", "straight", "curve"], width=14, state="readonly")
        connector.grid(row=row, column=1, sticky="ew", pady=3)
        connector.bind("<<ComboboxSelected>>", lambda _event: self.apply_properties())

        row += 1
        ttk.Label(parent, text="对齐", font=("", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(14, 4))
        row += 1
        buttons = [
            ("左对齐", self.align_left),
            ("水平居中", self.align_center),
            ("顶对齐", self.align_top),
            ("垂直居中", self.align_middle),
            ("横向分布", self.distribute_h),
            ("纵向分布", self.distribute_v),
        ]
        for i, (text, command) in enumerate(buttons):
            ttk.Button(parent, text=text, command=command).grid(row=row + i // 2, column=i % 2, sticky="ew", padx=2, pady=2)

        row += 4
        self.metrics_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.metrics_var, justify="left").grid(row=row, column=0, columnspan=2, sticky="w", pady=(14, 0))

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", lambda _event: self.request_redraw())
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())
        self.root.bind("<Control-c>", lambda _event: self.copy_selected())
        self.root.bind("<Control-v>", lambda _event: self.paste_clipboard())
        self.root.bind("<Control-s>", lambda _event: self.save_document())
        self.root.bind("<Control-o>", lambda _event: self.open_document())
        self.root.bind("<Delete>", lambda _event: self.delete_selected())
        self.root.bind("<Escape>", lambda _event: self.cancel_current())
        self.root.bind("<Control-Prior>", lambda _event: self.prev_page())
        self.root.bind("<Control-Next>", lambda _event: self.next_page())

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self.connector_start_id = None
        label = DEFAULT_LABELS.get(tool, "选择" if tool == "select" else tool)
        self.status_var.set(f"当前工具：{label}")
        self.refresh_tool_buttons()

    def refresh_tool_buttons(self) -> None:
        for tool, button in self.tool_buttons.items():
            if tool == self.tool:
                button.configure(bg=THEME["accent"], fg="#ffffff", activebackground=THEME["accent_dark"], activeforeground="#ffffff")
            else:
                button.configure(bg=THEME["tool_bg"], fg=THEME["tool_text"], activebackground=THEME["accent_soft"], activeforeground=THEME["accent"])

    def screen_to_world(self, event_or_point) -> Point:
        x = event_or_point.x
        y = event_or_point.y
        return Point((x - self.offset.x) / self.zoom, (y - self.offset.y) / self.zoom)

    def world_for_drawing(self, event_or_point) -> Point:
        point = self.screen_to_world(event_or_point)
        if self.snap_var.get():
            return Point(snap(point.x, self.document.grid_size), snap(point.y, self.document.grid_size))
        return point

    def on_mouse_down(self, event) -> None:
        self.canvas.focus_set()
        self.drag_start_screen = Point(event.x, event.y)
        self.drag_start_world = self.world_for_drawing(event)
        self.last_drag_world = self.drag_start_world.copy()
        self.marquee = None
        self.preview_shape = None
        self.resize_start_bounds = {}
        self.resize_handle = ""

        if self.tool == "pan":
            self.drag_mode = "pan"
            return

        if self.tool == "connector":
            hit = self.hit_test(self.screen_to_world(event))
            if hit and hit.type != "connector":
                if not self.connector_start_id:
                    self.connector_start_id = hit.id
                    self.selected_ids = {hit.id}
                    self.status_var.set("请选择连接线终点")
                else:
                    self.history.push(self.document)
                    connector = make_shape("connector", 0, 0, 0, 0)
                    connector.connection = Connection(self.connector_start_id, hit.id, self.prop_vars["connector"].get())
                    self.document.shapes.append(connector)
                    self.connector_start_id = None
                    self.set_tool("select")
                    self._record_replay("创建连接线")
                self.redraw()
            return

        if self.tool == "pen":
            self.drag_start_world = self.screen_to_world(event)
            self.last_drag_world = self.drag_start_world.copy()
            self.drag_mode = "pen"
            self.preview_shape = make_shape("pen", self.drag_start_world.x, self.drag_start_world.y, 0, 0)
            self.apply_current_line_style(self.preview_shape)
            self.redraw()
            return

        if self.tool == "select":
            handle = self.hit_resize_handle(Point(event.x, event.y))
            if handle:
                self.history.push(self.document)
                self.drag_mode = "resize"
                self.resize_handle = handle
                self.resize_start_bounds = {shape.id: shape.bounds() for shape in self.selected_shapes()}
                return
            hit = self.hit_test(self.screen_to_world(event))
            if hit:
                if event.state & 0x0001:
                    if hit.id in self.selected_ids:
                        self.selected_ids.remove(hit.id)
                    else:
                        self.selected_ids.add(hit.id)
                elif hit.id not in self.selected_ids:
                    self.selected_ids = {hit.id}
                self.history.push(self.document)
                self.drag_mode = "move"
                self.refresh_inspector()
            else:
                self.selected_ids.clear()
                self.drag_mode = "marquee"
                self.marquee = (Point(event.x, event.y), Point(event.x, event.y))
                self.refresh_inspector()
            self.redraw()
            return

        self.drag_mode = "draw"
        self.preview_shape = self.shape_from_drag(self.tool, self.drag_start_world, self.drag_start_world)
        self.redraw()

    def on_mouse_drag(self, event) -> None:
        if not self.drag_start_screen or not self.drag_start_world:
            return
        current_world = self.screen_to_world(event) if self.drag_mode == "pen" else self.world_for_drawing(event)
        if self.drag_mode == "pan":
            self.offset.x += event.x - self.drag_start_screen.x
            self.offset.y += event.y - self.drag_start_screen.y
            self.drag_start_screen = Point(event.x, event.y)
        elif self.drag_mode == "move" and self.last_drag_world:
            dx = current_world.x - self.last_drag_world.x
            dy = current_world.y - self.last_drag_world.y
            for shape in self.selected_shapes():
                shape.move(dx, dy)
            self.last_drag_world = current_world
            self.refresh_inspector()
        elif self.drag_mode == "resize":
            self.resize_selected_from_handle(current_world)
        elif self.drag_mode == "marquee":
            self.marquee = (self.drag_start_screen, Point(event.x, event.y))
        elif self.drag_mode == "pen" and self.preview_shape:
            self.append_pen_point(self.preview_shape, current_world)
        elif self.drag_mode == "draw":
            self.preview_shape = self.shape_from_drag(self.tool, self.drag_start_world, current_world)
        self.request_redraw()

    def on_mouse_up(self, event) -> None:
        completed_mode = self.drag_mode
        moved = (
            completed_mode == "move"
            and self.drag_start_world is not None
            and self.last_drag_world is not None
            and (abs(self.last_drag_world.x - self.drag_start_world.x) > 0.1 or abs(self.last_drag_world.y - self.drag_start_world.y) > 0.1)
        )
        if self.drag_mode == "pen" and self.preview_shape:
            final_point = self.screen_to_world(event)
            self.append_pen_point(self.preview_shape, final_point)
            if len(self.preview_shape.points) >= 2:
                recognized_shape: Shape | None = None
                if self.auto_recognize_var.get():
                    result = recognize_stroke(self.preview_shape.points)
                    if result:
                        recognized_shape = shape_from_recognition(self.preview_shape, result)
                self.history.push(self.document)
                if recognized_shape is not None:
                    self.document.shapes.append(recognized_shape)
                    self.selected_ids = {recognized_shape.id}
                    self.status_var.set(f"已识别为 {result.name}（{result.detail}）")
                    self._record_replay(f"智能识别：{result.name}")
                else:
                    self.document.shapes.append(self.preview_shape)
                    self.selected_ids = {self.preview_shape.id}
                    self._record_replay("画笔标注")
        elif self.drag_mode == "draw" and self.preview_shape:
            if abs(self.preview_shape.w) > 4 or abs(self.preview_shape.h) > 4 or self.preview_shape.type in {"line", "arrow"}:
                self.history.push(self.document)
                self.document.shapes.append(self.preview_shape)
                self.selected_ids = {self.preview_shape.id}
                if self.tool != "text":
                    self.set_tool("select")
                self._record_replay("绘制图形")
        elif self.drag_mode == "marquee" and self.marquee:
            start, end = self.marquee
            left, right = sorted([(start.x - self.offset.x) / self.zoom, (end.x - self.offset.x) / self.zoom])
            top, bottom = sorted([(start.y - self.offset.y) / self.zoom, (end.y - self.offset.y) / self.zoom])
            self.selected_ids = {shape.id for shape in self.document.shapes if rect_intersects_shape((left, top, right, bottom), shape)}
        elif moved:
            self._record_replay("移动图形")
        elif completed_mode == "resize":
            self._record_replay("缩放图形")
        self.preview_shape = None
        self.marquee = None
        self.drag_mode = ""
        self.refresh_inspector()
        self.request_redraw()

    def on_mouse_move(self, event) -> None:
        point = self.screen_to_world(event)
        self.cursor_var.set(f"x: {point.x:.0f}, y: {point.y:.0f}  缩放: {self.zoom * 100:.0f}%")

    def on_mouse_wheel(self, event) -> None:
        if event.state & 0x0004 and self._scale_selected_images(1.08 if event.delta > 0 else 1 / 1.08):
            return
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        before = self.screen_to_world(event)
        self.zoom = max(0.25, min(2.5, self.zoom * factor))
        self.offset.x = event.x - before.x * self.zoom
        self.offset.y = event.y - before.y * self.zoom
        self.request_redraw()

    def _scale_selected_images(self, factor: float) -> bool:
        shapes = [shape for shape in self.selected_shapes() if shape.type == "image"]
        if not shapes:
            return False
        self.history.push(self.document)
        for shape in shapes:
            center = shape.center()
            new_w = max(24, min(self.document.width * 2, abs(shape.w) * factor))
            new_h = max(24, min(self.document.height * 2, abs(shape.h) * factor))
            shape.x = center.x - new_w / 2
            shape.y = center.y - new_h / 2
            shape.w = new_w
            shape.h = new_h
            shape.scale_x = 1.0
            shape.scale_y = 1.0
        self.refresh_inspector()
        self.status_var.set("在线图形缩放：Ctrl + 鼠标滚轮")
        self._record_replay("缩放在线图形")
        self.request_redraw()
        return True

    def on_double_click(self, event) -> None:
        hit = self.hit_test(self.screen_to_world(event))
        if not hit:
            return
        text = simpledialog.askstring("编辑文本", "文本内容：", initialvalue=hit.text or hit.name, parent=self.root)
        if text is not None:
            self.history.push(self.document)
            hit.text = text
            self.selected_ids = {hit.id}
            self.refresh_inspector()
            self._record_replay("编辑文本")
            self.redraw()

    def shape_from_drag(self, tool: str, start: Point, end: Point) -> Shape:
        left = min(start.x, end.x)
        top = min(start.y, end.y)
        w = max(8, abs(end.x - start.x))
        h = max(8, abs(end.y - start.y))
        if tool in {"line", "arrow"}:
            shape = make_shape(tool, start.x, start.y, end.x - start.x, end.y - start.y)
            shape.points = [start.copy(), end.copy()]
            return shape
        shape_type = "round_rect" if tool == "round_rect" else tool
        if tool in {"cube", "sphere"}:
            size = max(w, h)
            left = start.x if end.x >= start.x else start.x - size
            top = start.y if end.y >= start.y else start.y - size
            w = size
            h = size
        if tool == "text":
            h = max(44, h)
        return make_shape(shape_type, left, top, w, h)

    def append_pen_point(self, shape: Shape, point: Point) -> None:
        if shape.points:
            last = shape.points[-1]
            if (last.x - point.x) ** 2 + (last.y - point.y) ** 2 < 2.0:
                return
        shape.points.append(point.copy())
        left, top, right, bottom = shape.bounds()
        shape.x = left
        shape.y = top
        shape.w = max(1, right - left)
        shape.h = max(1, bottom - top)

    def apply_current_line_style(self, shape: Shape) -> None:
        shape.style.stroke = self.prop_vars["stroke"].get() or shape.style.stroke
        shape.style.width = max(1, int(self._float_var("line_width", shape.style.width)))
        shape.style.dash = self.prop_vars["dash"].get() or shape.style.dash

    def hit_test(self, point: Point) -> Shape | None:
        for shape in reversed(self.document.shapes):
            if shape_hit(shape, point):
                return shape
        return None

    def hit_resize_handle(self, screen_point: Point) -> str:
        if len(self.selected_ids) != 1:
            return ""
        shape = self.selected_shapes()[0]
        if shape.type in {"line", "arrow", "connector", "pen"}:
            return ""
        left, top, right, bottom = shape.bounds()
        handles = {
            "nw": self.renderer.world_to_screen(Point(left, top), self.zoom, self.offset),
            "ne": self.renderer.world_to_screen(Point(right, top), self.zoom, self.offset),
            "se": self.renderer.world_to_screen(Point(right, bottom), self.zoom, self.offset),
            "sw": self.renderer.world_to_screen(Point(left, bottom), self.zoom, self.offset),
        }
        for name, point in handles.items():
            if abs(screen_point.x - point.x) <= 8 and abs(screen_point.y - point.y) <= 8:
                return name
        return ""

    def resize_selected_from_handle(self, current: Point) -> None:
        if not self.resize_handle:
            return
        for shape in self.selected_shapes():
            start = self.resize_start_bounds.get(shape.id)
            if not start:
                continue
            left, top, right, bottom = start
            if "w" in self.resize_handle:
                left = min(current.x, right - 8)
            if "e" in self.resize_handle:
                right = max(current.x, left + 8)
            if "n" in self.resize_handle:
                top = min(current.y, bottom - 8)
            if "s" in self.resize_handle:
                bottom = max(current.y, top + 8)
            if shape.type in {"cube", "sphere"}:
                size = max(right - left, bottom - top, 8)
                if "w" in self.resize_handle:
                    left = right - size
                else:
                    right = left + size
                if "n" in self.resize_handle:
                    top = bottom - size
                else:
                    bottom = top + size
            shape.resize_from_bounds(left, top, right, bottom)
        self.refresh_inspector()

    def selected_shapes(self) -> list[Shape]:
        return [shape for shape in self.document.shapes if shape.id in self.selected_ids]

    def refresh_inspector(self) -> None:
        shapes = self.selected_shapes()
        self.metrics_var.set(f"图元数量：{len(self.document.shapes)}\n选中数量：{len(shapes)}\n画布：{self.document.width} × {self.document.height}")
        if not shapes:
            self.selection_var.set("未选择")
            return
        first = shapes[0]
        self.selection_var.set(f"{first.name or first.type}  ({len(shapes)} 个)" if len(shapes) > 1 else first.name or first.type)
        self.prop_vars["x"].set(str(round(first.x, 1)))
        self.prop_vars["y"].set(str(round(first.y, 1)))
        self.prop_vars["w"].set(str(round(first.w, 1)))
        self.prop_vars["h"].set(str(round(first.h, 1)))
        self.prop_vars["rotation"].set(str(round(first.rotation, 1)))
        self.prop_vars["line_width"].set(str(first.style.width))
        self.prop_vars["text"].set(first.text)
        self.prop_vars["fill"].set(first.style.fill)
        self.prop_vars["stroke"].set(first.style.stroke)
        self.prop_vars["dash"].set(first.style.dash)
        if first.connection:
            self.prop_vars["connector"].set(first.connection.style)

    def apply_properties(self) -> None:
        shapes = self.selected_shapes()
        if not shapes:
            return
        self.history.push(self.document)
        first = shapes[0]
        dx = self._float_var("x", first.x) - first.x
        dy = self._float_var("y", first.y) - first.y
        for shape in shapes:
            shape.move(dx, dy)
            if shape.type != "pen":
                new_w = max(4, self._float_var("w", shape.w))
                new_h = max(4, self._float_var("h", shape.h))
                if shape.type in {"cube", "sphere"}:
                    new_h = new_w
                shape.w = new_w
                shape.h = new_h
            shape.rotation = self._float_var("rotation", shape.rotation) % 360
            shape.style.width = max(1, int(self._float_var("line_width", shape.style.width)))
            shape.text = self.prop_vars["text"].get()
            shape.style.fill = self.prop_vars["fill"].get() or shape.style.fill
            shape.style.stroke = self.prop_vars["stroke"].get() or shape.style.stroke
            shape.style.dash = self.prop_vars["dash"].get()
            if shape.connection:
                shape.connection.style = self.prop_vars["connector"].get()
        self._record_replay("修改属性")
        self.redraw()

    def _float_var(self, key: str, fallback: float) -> float:
        try:
            return float(self.prop_vars[key].get())
        except Exception:
            return fallback

    def pick_color(self, key: str) -> None:
        color = colorchooser.askcolor(color=self.prop_vars[key].get(), parent=self.root)[1]
        if color:
            self.prop_vars[key].set(color)
            self.apply_properties()

    def apply_swatch(self, color: str) -> None:
        self.prop_vars["fill"].set(color)
        self.apply_properties()

    def request_redraw(self, delay_ms: int = 12) -> None:
        if self._redraw_after_id is not None:
            return
        self._redraw_after_id = self.root.after(delay_ms, self._run_scheduled_redraw)

    def _run_scheduled_redraw(self) -> None:
        self._redraw_after_id = None
        self.redraw()

    def redraw(self) -> None:
        width = max(320, self.canvas.winfo_width())
        height = max(240, self.canvas.winfo_height())
        document = self.document
        if self.preview_shape:
            document = self.document.copy()
            document.shapes.append(self.preview_shape)
        image = self.renderer.render(document, width, height, self.zoom, self.offset, self.selected_ids, self.show_grid_var.get(), self.marquee)
        self._photo = ImageTk.PhotoImage(image)
        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.refresh_inspector()

    def _record_replay(self, action: str) -> None:
        snapshot = self.document.to_dict()
        # 跳过与上一帧完全相同的快照，避免回放里堆叠无变化的重复帧。
        if self.replay_frames and self.replay_frames[-1]["document"] == snapshot:
            return
        self.replay_frames.append({"action": action, "document": snapshot})
        if len(self.replay_frames) > self.max_replay_frames:
            self.replay_frames.pop(0)

    def open_asset_search_window(self) -> None:
        if self._asset_window and self._asset_window.winfo_exists():
            self._asset_window.lift()
            return

        window = tk.Toplevel(self.root)
        window.title("在线图形库")
        window.geometry("940x640")
        window.transient(self.root)
        self._asset_window = window
        self._asset_result_photos = []

        search_var = tk.StringVar(value="树形图")
        status_var = tk.StringVar(value="连接在线图形库，优先检索 SVG、图标、矢量图和示意图。")

        top = ttk.Frame(window, padding=(14, 12))
        top.pack(fill="x")
        entry = ttk.Entry(top, textvariable=search_var, width=34)
        entry.pack(side="left", fill="x", expand=True)
        search_button = ttk.Button(top, text="搜索")
        search_button.pack(side="left", padx=(8, 0))

        result_canvas = tk.Canvas(window, bg=THEME["ribbon"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=result_canvas.yview)
        result_frame = ttk.Frame(result_canvas, padding=12)
        result_frame.bind("<Configure>", lambda _event: result_canvas.configure(scrollregion=result_canvas.bbox("all")))
        result_window = result_canvas.create_window((0, 0), window=result_frame, anchor="nw")
        result_canvas.bind("<Configure>", lambda event: result_canvas.itemconfigure(result_window, width=event.width))
        result_canvas.configure(yscrollcommand=scrollbar.set)
        result_canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 10))
        scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=(0, 10))

        ttk.Label(window, textvariable=status_var).pack(anchor="w", padx=14, pady=(0, 10))

        def clear_results() -> None:
            for child in result_frame.winfo_children():
                child.destroy()
            self._asset_result_photos.clear()

        def set_busy(text: str) -> None:
            if not window.winfo_exists():
                return
            status_var.set(text)
            search_button.configure(state="disabled")

        def set_ready(text: str) -> None:
            if not window.winfo_exists():
                return
            status_var.set(text)
            search_button.configure(state="normal")

        def run_search() -> None:
            query = search_var.get().strip()
            if not query:
                set_ready("请输入关键词。")
                return
            self._asset_search_token += 1
            token = self._asset_search_token
            clear_results()
            set_busy(f"正在搜索：{query}")

            def worker() -> None:
                try:
                    results = search_assets(query, limit=18)
                except Exception as exc:
                    self.root.after(0, lambda: set_ready(f"搜索失败：{exc}"))
                    return
                self.root.after(0, lambda: show_results(token, query, results))

            threading.Thread(target=worker, daemon=True).start()

        def show_results(token: int, query: str, results: list[AssetResult]) -> None:
            if token != self._asset_search_token or not window.winfo_exists():
                return
            clear_results()
            if not results:
                set_ready(f"没有找到与“{query}”相关的图形。")
                return
            set_ready(f"找到 {len(results)} 个图形。插入时会下载中等尺寸并写入工程文件。")
            for index, result in enumerate(results):
                item = ttk.Frame(result_frame, padding=8, relief="solid")
                item.grid(row=index, column=0, sticky="ew", padx=4, pady=5)
                item.columnconfigure(1, weight=1)
                result_frame.columnconfigure(0, weight=1)
                thumb_label = ttk.Label(item, width=24, anchor="center")
                thumb_label.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 10))
                title = result.title[:86] + ("..." if len(result.title) > 86 else "")
                ttk.Label(item, text=title, wraplength=560, justify="left", font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=1, sticky="ew")
                meta = result.source + (f" · {result.license}" if result.license else "")
                ttk.Label(item, text=meta, foreground=THEME["subtext"]).grid(row=1, column=1, sticky="w", pady=(4, 0))
                ttk.Button(item, text="插入画布", command=lambda r=result: insert_asset(r)).grid(row=0, column=2, rowspan=3, sticky="e", padx=(12, 0))
                load_thumb_async(token, result, thumb_label)

        def load_thumb_async(token: int, result: AssetResult, label: ttk.Label) -> None:
            def worker() -> None:
                try:
                    thumb = load_thumbnail(result)
                except Exception:
                    thumb = placeholder_thumbnail(result.title)

                def apply_thumb() -> None:
                    if token != self._asset_search_token or not label.winfo_exists():
                        return
                    photo = ImageTk.PhotoImage(thumb)
                    self._asset_result_photos.append(photo)
                    label.configure(image=photo, text="")

                self.root.after(0, apply_thumb)

            threading.Thread(target=worker, daemon=True).start()

        def insert_asset(result: AssetResult) -> None:
            set_busy(f"正在下载并缓存图形：{result.title[:24]}")

            def worker() -> None:
                try:
                    asset = download_asset(result)
                except Exception as exc:
                    self.root.after(0, lambda: set_ready(f"插入失败：{exc}"))
                    return
                self.root.after(0, lambda: self._insert_cached_asset(result, asset, status_var, search_button))

            threading.Thread(target=worker, daemon=True).start()

        search_button.configure(command=run_search)
        entry.bind("<Return>", lambda _event: run_search())

        def close() -> None:
            if self._asset_window is window:
                self._asset_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        entry.focus_set()

    def _insert_cached_asset(self, result: AssetResult, asset, status_var: tk.StringVar, search_button: ttk.Button) -> None:
        if not search_button.winfo_exists():
            return
        max_w = 320
        max_h = 240
        scale = min(max_w / max(1, asset.width), max_h / max(1, asset.height), 1.0)
        w = max(32, asset.width * scale)
        h = max(32, asset.height * scale)
        x = max(0, (self.document.width - w) / 2)
        y = max(0, (self.document.height - h) / 2)

        shape = make_shape("image", x, y, w, h)
        shape.name = result.title or "在线图形"
        shape.image_data = asset.data
        shape.image_mime = asset.mime
        shape.image_path = str(asset.path)
        shape.source_url = result.page_url or result.image_url
        shape.text = ""

        self.history.push(self.document)
        self.document.shapes.append(shape)
        self.selected_ids = {shape.id}
        self.set_tool("select")
        self.status_var.set(f"已插入在线图形：{shape.name}")
        status_var.set("已插入画布，图形已写入工程数据，断网后仍可显示和导出。")
        search_button.configure(state="normal")
        self._record_replay("插入在线图形")
        self.redraw()

    def open_text_flow_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("文本生成流程图")
        dialog.geometry("620x430")
        dialog.transient(self.root)

        ttk.Label(dialog, text="输入箭头式流程描述，支持“是/否”分支：").pack(anchor="w", padx=14, pady=(14, 6))
        editor = tk.Text(dialog, height=14, wrap="word", font=("Microsoft YaHei UI", 10), undo=True)
        editor.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        editor.insert(
            "1.0",
            "开始 -> 接收原始数据 -> 数据完整?\n"
            "是 -> 清洗与标准化 -> 生成统计图表 -> 保存处理记录 -> 结束\n"
            "否 -> 生成错误清单 -> 通知用户补充数据 -> 异常结束",
        )

        button_row = ttk.Frame(dialog, padding=(14, 8))
        button_row.pack(fill="x")

        def generate() -> None:
            source = editor.get("1.0", "end").strip()
            try:
                document = generate_flowchart_from_text(source)
            except Exception as exc:
                messagebox.showerror("生成失败", str(exc), parent=dialog)
                return
            self.history.push(self.document)
            self.document = document
            self.current_path = None
            self.selected_ids.clear()
            self._sync_current_page_document()
            self.status_var.set("已根据文本生成流程图")
            self._record_replay("文本生成流程图")
            self.redraw()
            dialog.destroy()

        ttk.Button(button_row, text="生成并替换画布", command=generate).pack(side="right", padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right", padx=4)

    def open_replay_window(self) -> None:
        if not self.replay_frames:
            self._record_replay("当前画布")

        window = tk.Toplevel(self.root)
        window.title("操作回放")
        window.geometry("900x650")
        window.transient(self.root)

        self._replay_canvas = tk.Canvas(window, bg=THEME["viewport"], highlightthickness=0)
        self._replay_canvas.pack(fill="both", expand=True, padx=14, pady=(14, 6))
        self._replay_image_id = None
        self._replay_photo = None
        self._replay_status_var = tk.StringVar()
        ttk.Label(window, textvariable=self._replay_status_var).pack(anchor="w", padx=14)

        controls = ttk.Frame(window, padding=(14, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="上一步", command=lambda: self._set_replay_index(self._replay_index - 1)).pack(side="left", padx=3)
        ttk.Button(controls, text="播放/暂停", command=self._toggle_replay).pack(side="left", padx=3)
        ttk.Button(controls, text="下一步", command=lambda: self._set_replay_index(self._replay_index + 1)).pack(side="left", padx=3)
        ttk.Button(controls, text="导出 GIF", command=self.export_replay_gif).pack(side="right", padx=3)
        self._replay_scale = ttk.Scale(
            controls,
            from_=0,
            to=max(0, len(self.replay_frames) - 1),
            command=lambda value: self._on_replay_scale(float(value)),
        )
        self._replay_scale.pack(side="left", fill="x", expand=True, padx=10)

        def close() -> None:
            self._replay_playing = False
            if self._replay_after_id:
                self.root.after_cancel(self._replay_after_id)
                self._replay_after_id = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        self._replay_canvas.bind("<Configure>", lambda _event: self._render_replay_frame(self._replay_index))
        self._set_replay_index(0)

    def _set_replay_index(self, index: int) -> None:
        if not self.replay_frames:
            return
        self._replay_index = max(0, min(len(self.replay_frames) - 1, index))
        self._render_replay_frame(self._replay_index)

    def _on_replay_scale(self, value: float) -> None:
        if self._syncing_replay_scale:
            return
        self._set_replay_index(int(value))

    def _toggle_replay(self) -> None:
        self._replay_playing = not self._replay_playing
        if self._replay_playing:
            self._play_next_replay_frame()
        elif self._replay_after_id:
            self.root.after_cancel(self._replay_after_id)
            self._replay_after_id = None

    def _play_next_replay_frame(self) -> None:
        if not self._replay_playing:
            return
        if self._replay_index >= len(self.replay_frames) - 1:
            self._replay_playing = False
            return
        self._set_replay_index(self._replay_index + 1)
        self._replay_after_id = self.root.after(700, self._play_next_replay_frame)

    def _render_replay_frame(self, index: int) -> None:
        if not self._replay_canvas or not self.replay_frames:
            return
        frame = self.replay_frames[index]
        document = Document.from_dict(frame["document"])
        width = max(640, self._replay_canvas.winfo_width())
        height = max(420, self._replay_canvas.winfo_height())
        zoom = min((width - 40) / document.width, (height - 40) / document.height, 1.0)
        zoom = max(0.12, zoom)
        offset = Point((width - document.width * zoom) / 2, (height - document.height * zoom) / 2)
        image = self.renderer.render(document, width, height, zoom, offset, set(), True, None)
        self._replay_photo = ImageTk.PhotoImage(image)
        if self._replay_image_id is None:
            self._replay_image_id = self._replay_canvas.create_image(0, 0, anchor="nw", image=self._replay_photo)
        else:
            self._replay_canvas.itemconfigure(self._replay_image_id, image=self._replay_photo)
        if self._replay_status_var:
            self._replay_status_var.set(f"{index + 1}/{len(self.replay_frames)}  {frame['action']}")
        if self._replay_scale:
            self._syncing_replay_scale = True
            try:
                self._replay_scale.set(index)
            finally:
                self._syncing_replay_scale = False

    def export_replay_gif(self) -> None:
        if not self.replay_frames:
            messagebox.showinfo("导出 GIF", "暂无可导出的回放帧。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            filetypes=[("GIF 动图", "*.gif")],
            title="导出回放动图",
        )
        if not path:
            return
        frames_data = [dict(frame) for frame in self.replay_frames]
        if self._replay_status_var:
            self._replay_status_var.set("正在渲染 GIF……")

        def worker() -> None:
            try:
                canvas_w, canvas_h = 960, 640
                images = []
                for frame in frames_data:
                    document = Document.from_dict(frame["document"])
                    zoom = min((canvas_w - 40) / document.width, (canvas_h - 40) / document.height, 1.0)
                    zoom = max(0.12, zoom)
                    offset = Point((canvas_w - document.width * zoom) / 2, (canvas_h - document.height * zoom) / 2)
                    image = self.renderer.render(document, canvas_w, canvas_h, zoom, offset, set(), True, None)
                    images.append(image.convert("RGB"))
                if not images:
                    return
                images[0].save(
                    path,
                    save_all=True,
                    append_images=images[1:],
                    duration=700,
                    loop=0,
                )

                def done() -> None:
                    if self._replay_status_var:
                        self._replay_status_var.set(f"已导出 GIF（{len(images)} 帧）：{path}")
                    self.status_var.set("回放已导出为 GIF")

                self.root.after(0, done)
            except Exception as exc:  # noqa: BLE001 - surface any render/save error to the user
                self.root.after(0, lambda: messagebox.showerror("导出 GIF 失败", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def open_algorithm_demo(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("图形学算法演示")
        window.geometry("1120x650")
        window.transient(self.root)

        top = ttk.Frame(window, padding=(14, 12))
        top.pack(fill="x")
        self._algorithm_choice_var = tk.StringVar(value=ALGORITHMS[0])
        chooser = ttk.Combobox(top, textvariable=self._algorithm_choice_var, values=ALGORITHMS, state="readonly", width=28)
        chooser.pack(side="left")
        chooser.bind("<<ComboboxSelected>>", lambda _event: self._set_algorithm_demo(self._algorithm_choice_var.get()))
        ttk.Button(top, text="播放/暂停", command=self._toggle_algorithm_demo).pack(side="left", padx=8)
        ttk.Button(top, text="上一步", command=lambda: self._set_algorithm_index(self._algorithm_index - 1)).pack(side="left", padx=3)
        ttk.Button(top, text="下一步", command=lambda: self._set_algorithm_index(self._algorithm_index + 1)).pack(side="left", padx=3)
        ttk.Button(top, text="重置", command=lambda: self._set_algorithm_index(0)).pack(side="left", padx=3)

        body = ttk.Frame(window, padding=(14, 0, 14, 12))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(body, padding=(12, 0, 0, 0))
        right.pack(side="right", fill="y")

        self._algorithm_canvas = tk.Canvas(left, width=720, height=460, bg=THEME["viewport"], highlightthickness=0)
        self._algorithm_canvas.pack(fill="both", expand=True, pady=(0, 8))
        self._algorithm_frames = []
        self._algorithm_status_var = tk.StringVar()
        ttk.Label(left, textvariable=self._algorithm_status_var).pack(anchor="w")

        ttk.Label(right, text="算法说明", font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
        info_frame = ttk.Frame(right)
        info_frame.pack(fill="both", expand=True)
        self._algorithm_info_text = tk.Text(
            info_frame,
            width=40,
            height=28,
            wrap="word",
            bg="#ffffff",
            fg="#1d2433",
            relief="solid",
            bd=1,
            padx=10,
            pady=10,
            font=("Microsoft YaHei UI", 10),
        )
        info_scroll = ttk.Scrollbar(info_frame, orient="vertical", command=self._algorithm_info_text.yview)
        self._algorithm_info_text.configure(yscrollcommand=info_scroll.set, state="disabled")
        self._algorithm_info_text.pack(side="left", fill="both", expand=True)
        info_scroll.pack(side="right", fill="y")

        def close() -> None:
            self._algorithm_playing = False
            if self._algorithm_after_id:
                self.root.after_cancel(self._algorithm_after_id)
                self._algorithm_after_id = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        self._set_algorithm_demo(ALGORITHMS[0])

    def _set_algorithm_demo(self, name: str) -> None:
        self._algorithm_playing = False
        if self._algorithm_after_id:
            self.root.after_cancel(self._algorithm_after_id)
            self._algorithm_after_id = None
        self._algorithm_frames = build_algorithm_frames(name)
        self._set_algorithm_index(0)

    def _set_algorithm_index(self, index: int) -> None:
        if not self._algorithm_frames:
            return
        self._algorithm_index = max(0, min(len(self._algorithm_frames) - 1, index))
        self._render_algorithm_frame()

    def _toggle_algorithm_demo(self) -> None:
        self._algorithm_playing = not self._algorithm_playing
        if self._algorithm_playing:
            self._play_next_algorithm_frame()
        elif self._algorithm_after_id:
            self.root.after_cancel(self._algorithm_after_id)
            self._algorithm_after_id = None

    def _play_next_algorithm_frame(self) -> None:
        if not self._algorithm_playing:
            return
        if self._algorithm_index >= len(self._algorithm_frames) - 1:
            self._algorithm_playing = False
            return
        self._set_algorithm_index(self._algorithm_index + 1)
        self._algorithm_after_id = self.root.after(120, self._play_next_algorithm_frame)

    def _render_algorithm_frame(self) -> None:
        if not self._algorithm_canvas or not self._algorithm_frames:
            return
        frame = self._algorithm_frames[self._algorithm_index]
        self._algorithm_canvas.delete("all")
        for item in frame["items"]:
            self._draw_algorithm_item(item)
        if self._algorithm_status_var:
            self._algorithm_status_var.set(f"{self._algorithm_index + 1}/{len(self._algorithm_frames)}  {frame['caption']}")
        self._update_algorithm_info(frame)

    def _update_algorithm_info(self, frame: dict) -> None:
        if not self._algorithm_info_text or not self._algorithm_choice_var:
            return
        text = algorithm_explanation(
            self._algorithm_choice_var.get(),
            frame.get("detail", ""),
            self._algorithm_index,
            len(self._algorithm_frames),
        )
        self._algorithm_info_text.configure(state="normal")
        self._algorithm_info_text.delete("1.0", "end")
        self._algorithm_info_text.insert("1.0", text)
        self._algorithm_info_text.configure(state="disabled")

    def _draw_algorithm_item(self, item: dict) -> None:
        canvas = self._algorithm_canvas
        if not canvas:
            return
        item_type = item["type"]
        if item_type == "rect":
            canvas.create_rectangle(*item["coords"], fill=item.get("fill", ""), outline=item.get("outline", ""), width=item.get("width", 1))
        elif item_type == "oval":
            canvas.create_oval(*item["coords"], fill=item.get("fill", ""), outline=item.get("outline", "#1d2433"), width=item.get("width", 1))
        elif item_type == "line":
            canvas.create_line(*item["coords"], fill=item.get("fill", "#1d2433"), width=item.get("width", 1), dash=item.get("dash", ""))
        elif item_type == "polygon":
            points = [value for point in item["points"] for value in point]
            canvas.create_polygon(points, fill=item.get("fill", ""), outline=item.get("outline", "#1d2433"), width=item.get("width", 1))
        elif item_type == "point":
            x, y = item["coords"]
            size = item.get("size", 4)
            canvas.create_oval(x - size, y - size, x + size, y + size, fill=item.get("fill", "#1d8a99"), outline=item.get("outline", ""))
        elif item_type == "text":
            canvas.create_text(*item["coords"], text=item.get("text", ""), fill=item.get("fill", "#1d2433"), anchor=item.get("anchor", "center"), font=item.get("font", ("Microsoft YaHei UI", 10)))

    def new_document(self) -> None:
        if not self.confirm_discard():
            return
        self.document = Document()
        self.history = History()
        self.pages = [{"name": "页面 1", "document": self.document, "history": self.history}]
        self.current_page_index = 0
        self.selected_ids.clear()
        self.current_path = None
        self.replay_frames.clear()
        self.status_var.set("已新建工程")
        self._record_replay("新建工程")
        self._refresh_page_list()
        self.redraw()

    def open_document(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("VectorCraft JSON", "*.vcraft.json *.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            loaded = load_workspace(path)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))
            return
        if not loaded:
            messagebox.showerror("打开失败", "工程文件为空。")
            return
        self.pages = [{"name": name, "document": doc, "history": History()} for name, doc in loaded]
        self.current_page_index = 0
        first = self.pages[0]
        self.document = first["document"]
        self.history = first["history"]
        self.current_path = Path(path)
        self.selected_ids.clear()
        self.replay_frames.clear()
        self.status_var.set(f"已打开：{self.current_path.name}（{len(self.pages)} 个页面）")
        self._record_replay(f"打开工程：{self.current_path.name}")
        self._refresh_page_list()
        self.redraw()

    def save_document(self) -> None:
        path = self.current_path
        if not path:
            selected = filedialog.asksaveasfilename(
                defaultextension=".vcraft.json",
                filetypes=[("VectorCraft JSON", "*.vcraft.json"), ("JSON", "*.json")],
            )
            if not selected:
                return
            path = Path(selected)
        self._sync_current_page_document()
        try:
            if len(self.pages) > 1:
                save_workspace([(page["name"], page["document"]) for page in self.pages], path)
            else:
                save_json(self.document, path)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self.current_path = path
        self.status_var.set(f"已保存：{path.name}（{len(self.pages)} 个页面）")

    def export_png(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            export_png(self.document, path)
            self.status_var.set("已导出 PNG")

    def export_svg(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if path:
            export_svg(self.document, path)
            self.status_var.set("已导出 SVG")

    def load_template(self, name: str, record: bool = True) -> None:
        if record:
            self.history.push(self.document)
        if name == "flow":
            self.document = flowchart_template()
        elif name == "org":
            self.document = org_template()
        elif name == "circuit":
            self.document = circuit_template()
        elif name == "uml":
            self.document = uml_class_template()
        elif name == "gantt":
            self.document = gantt_template()
        elif name == "sequence":
            self.document = sequence_template()
        else:
            self.document = flowchart_template()
        self.current_path = None
        self.selected_ids.clear()
        self._sync_current_page_document()
        self.status_var.set("已载入模板")
        template_name = {
            "flow": "流程图模板",
            "org": "组织结构图模板",
            "circuit": "电路图模板",
            "uml": "UML 类图模板",
            "gantt": "甘特图模板",
            "sequence": "时序图模板",
        }.get(name, "模板")
        self._record_replay(f"载入{template_name}")
        self.redraw()

    def confirm_discard(self) -> bool:
        return messagebox.askyesno("确认", "当前工程未保存时会丢失，继续吗？")

    def undo(self) -> None:
        restored = self.history.undo(self.document)
        if restored:
            self.document = restored
            self.selected_ids.clear()
            self._sync_current_page_document()
            self.status_var.set("已撤销")
            self._record_replay("撤销")
            self.redraw()

    def redo(self) -> None:
        restored = self.history.redo(self.document)
        if restored:
            self.document = restored
            self.selected_ids.clear()
            self._sync_current_page_document()
            self.status_var.set("已重做")
            self._record_replay("重做")
            self.redraw()

    def copy_selected(self) -> None:
        self.clipboard = [shape.clone(0, 0) for shape in self.selected_shapes()]
        self.status_var.set(f"已复制 {len(self.clipboard)} 个图元")

    def paste_clipboard(self) -> None:
        if not self.clipboard:
            return
        self.history.push(self.document)
        pasted = [shape.clone(28, 28) for shape in self.clipboard]
        self.document.shapes.extend(pasted)
        self.selected_ids = {shape.id for shape in pasted}
        self._record_replay("粘贴图形")
        self.redraw()

    def delete_selected(self) -> None:
        if not self.selected_ids:
            return
        self.history.push(self.document)
        self.document.remove_ids(self.selected_ids)
        self.selected_ids.clear()
        self._record_replay("删除图形")
        self.redraw()

    def mirror_selected(self, axis: str) -> None:
        shapes = self.selected_shapes()
        if not shapes:
            return
        self.history.push(self.document)
        for shape in shapes:
            if axis == "x":
                shape.scale_x *= -1
            else:
                shape.scale_y *= -1
        self._record_replay("镜像图形")
        self.redraw()

    def bring_front(self) -> None:
        if not self.selected_ids:
            return
        self.history.push(self.document)
        selected = [shape for shape in self.document.shapes if shape.id in self.selected_ids]
        others = [shape for shape in self.document.shapes if shape.id not in self.selected_ids]
        self.document.shapes = others + selected
        self._record_replay("图层置顶")
        self.redraw()

    def send_back(self) -> None:
        if not self.selected_ids:
            return
        self.history.push(self.document)
        selected = [shape for shape in self.document.shapes if shape.id in self.selected_ids]
        others = [shape for shape in self.document.shapes if shape.id not in self.selected_ids]
        self.document.shapes = selected + others
        self._record_replay("图层置底")
        self.redraw()

    def clip_lines_to_rect(self) -> None:
        shapes = self.selected_shapes()
        rects = [shape for shape in shapes if shape.type not in {"line", "arrow", "connector"}]
        lines = [shape for shape in shapes if shape.type in {"line", "arrow", "connector"} and len(shape.points) >= 2]
        if not rects or not lines:
            messagebox.showinfo("线段裁剪", "请同时选中一个裁剪区域图形和至少一条线段。")
            return
        rect = rects[0].bounds()
        self.history.push(self.document)
        for line in lines:
            clipped = cohen_sutherland_clip(line.points[0], line.points[-1], rect)
            if clipped:
                line.points = [clipped[0], clipped[1]]
            else:
                line.points = []
        self._record_replay("线段裁剪")
        self.redraw()

    def align_left(self) -> None:
        self._align("left")

    def align_center(self) -> None:
        self._align("center")

    def align_top(self) -> None:
        self._align("top")

    def align_middle(self) -> None:
        self._align("middle")

    def _align(self, mode: str) -> None:
        shapes = self.selected_shapes()
        if len(shapes) < 2:
            return
        self.history.push(self.document)
        if mode == "left":
            target = min(shape.bounds()[0] for shape in shapes)
            for shape in shapes:
                shape.move(target - shape.bounds()[0], 0)
        elif mode == "center":
            target = sum(shape.center().x for shape in shapes) / len(shapes)
            for shape in shapes:
                shape.move(target - shape.center().x, 0)
        elif mode == "top":
            target = min(shape.bounds()[1] for shape in shapes)
            for shape in shapes:
                shape.move(0, target - shape.bounds()[1])
        elif mode == "middle":
            target = sum(shape.center().y for shape in shapes) / len(shapes)
            for shape in shapes:
                shape.move(0, target - shape.center().y)
        self._record_replay("对齐图形")
        self.redraw()

    def distribute_h(self) -> None:
        self._distribute("h")

    def distribute_v(self) -> None:
        self._distribute("v")

    def _distribute(self, axis: str) -> None:
        shapes = self.selected_shapes()
        if len(shapes) < 3:
            return
        self.history.push(self.document)
        if axis == "h":
            shapes.sort(key=lambda s: s.center().x)
            start = shapes[0].center().x
            end = shapes[-1].center().x
            step = (end - start) / (len(shapes) - 1)
            for i, shape in enumerate(shapes):
                shape.move(start + step * i - shape.center().x, 0)
        else:
            shapes.sort(key=lambda s: s.center().y)
            start = shapes[0].center().y
            end = shapes[-1].center().y
            step = (end - start) / (len(shapes) - 1)
            for i, shape in enumerate(shapes):
                shape.move(0, start + step * i - shape.center().y)
        self._record_replay("等距分布")
        self.redraw()

    def change_zoom(self, factor: float) -> None:
        self.zoom = max(0.25, min(2.5, self.zoom * factor))
        self.redraw()

    def open_mind_map_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("思维导图自动布局")
        dialog.geometry("680x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text="输入大纲，使用缩进表示层级（每 2 个空格或一个 Tab 为一级）：").pack(anchor="w", padx=14, pady=(14, 6))
        editor = tk.Text(dialog, height=18, wrap="word", font=("Microsoft YaHei UI", 10), undo=True)
        editor.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        editor.insert(
            "1.0",
            "VectorCraft 项目\n"
            "  基础能力\n"
            "    图元绘制\n"
            "    几何变换\n"
            "    Cohen-Sutherland 裁剪\n"
            "  创新功能\n"
            "    文本生成流程图\n"
            "    算法演示\n"
            "    思维导图\n"
            "    多页画布\n"
            "  工程化\n"
            "    JSON 工程文件\n"
            "    PNG / SVG 导出\n",
        )

        button_row = ttk.Frame(dialog, padding=(14, 8))
        button_row.pack(fill="x")

        def generate() -> None:
            source = editor.get("1.0", "end").strip()
            try:
                document = generate_mind_map_from_text(source)
            except Exception as exc:
                messagebox.showerror("生成失败", str(exc), parent=dialog)
                return
            self._replace_current_document(document, status="已生成思维导图", action="生成思维导图")
            dialog.destroy()

        def generate_as_new_page() -> None:
            source = editor.get("1.0", "end").strip()
            try:
                document = generate_mind_map_from_text(source)
            except Exception as exc:
                messagebox.showerror("生成失败", str(exc), parent=dialog)
                return
            self.add_page(document=document, name="思维导图", status="已新建思维导图页面")
            dialog.destroy()

        ttk.Button(button_row, text="生成到新页面", command=generate_as_new_page).pack(side="right", padx=4)
        ttk.Button(button_row, text="替换当前画布", command=generate).pack(side="right", padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right", padx=4)

    def open_function_plot_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("函数图像绘制")
        dialog.geometry("620x460")
        dialog.transient(self.root)

        ttk.Label(dialog, text="函数表达式（每行一个，支持 sin/cos/tan/exp/log/sqrt 等，使用变量 x，幂运算可用 ^ 或 **）：").pack(anchor="w", padx=14, pady=(14, 6))
        editor = tk.Text(dialog, height=8, wrap="word", font=("Consolas", 11), undo=True)
        editor.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        editor.insert("1.0", "sin(x)\ncos(x)\n0.3*x*sin(x)")

        params = ttk.Frame(dialog, padding=(14, 4))
        params.pack(fill="x")
        ttk.Label(params, text="x 最小值").grid(row=0, column=0, sticky="w", padx=4)
        x_min_var = tk.StringVar(value="-10")
        ttk.Entry(params, textvariable=x_min_var, width=10).grid(row=0, column=1, padx=4)
        ttk.Label(params, text="x 最大值").grid(row=0, column=2, sticky="w", padx=4)
        x_max_var = tk.StringVar(value="10")
        ttk.Entry(params, textvariable=x_max_var, width=10).grid(row=0, column=3, padx=4)
        ttk.Label(params, text="采样数").grid(row=0, column=4, sticky="w", padx=4)
        samples_var = tk.StringVar(value="600")
        ttk.Entry(params, textvariable=samples_var, width=8).grid(row=0, column=5, padx=4)

        button_row = ttk.Frame(dialog, padding=(14, 8))
        button_row.pack(fill="x")

        colors = ["#1d8a99", "#d1842f", "#6c55ad", "#4d8a3f", "#c33f4a"]

        def build_specs() -> list[PlotSpec]:
            try:
                x_min = float(x_min_var.get())
                x_max = float(x_max_var.get())
                samples = int(float(samples_var.get()))
            except ValueError as exc:
                raise ValueError("x 范围或采样数必须为数字。") from exc
            expressions = [line.strip() for line in editor.get("1.0", "end").splitlines() if line.strip()]
            if not expressions:
                raise ValueError("请至少输入一个表达式。")
            return [
                PlotSpec(expression=expr, x_min=x_min, x_max=x_max, samples=samples, color=colors[index % len(colors)])
                for index, expr in enumerate(expressions)
            ]

        def generate(as_new_page: bool) -> None:
            try:
                specs = build_specs()
                document = function_plot_document(specs)
            except Exception as exc:
                messagebox.showerror("生成失败", str(exc), parent=dialog)
                return
            if as_new_page:
                self.add_page(document=document, name="函数图像", status="已新建函数图像页面")
            else:
                self._replace_current_document(document, status="已生成函数图像", action="生成函数图像")
            dialog.destroy()

        ttk.Button(button_row, text="生成到新页面", command=lambda: generate(True)).pack(side="right", padx=4)
        ttk.Button(button_row, text="替换当前画布", command=lambda: generate(False)).pack(side="right", padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right", padx=4)

    def open_diagram_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("图表生成（文本驱动）")
        dialog.geometry("720x560")
        dialog.transient(self.root)

        examples = {
            "甘特图": (
                "gantt",
                "需求分析: 1-2\n"
                "数据结构与渲染: 2, 3\n"
                "基础图元与编辑: 3-5\n"
                "模板与智能生成: 6-7\n"
                "测试与答辩准备: 8-9\n"
                "M1 框架就绪 @ 2\n"
                "M2 功能完成 @ 7\n"
                "M3 答辩展示 @ 9\n",
            ),
            "UML 类图": (
                "uml",
                "class Shape\n"
                "  - id: str\n"
                "  - x, y, w, h: float\n"
                "  + move(dx, dy)\n"
                "  + clone(): Shape\n"
                "class Style\n"
                "  - fill: str\n"
                "  - stroke: str\n"
                "class Document\n"
                "  - shapes: List[Shape]\n"
                "  + to_dict(): dict\n"
                "Shape --> Style : 组合\n"
                "Document --> Shape : 聚合 0..*\n"
                "Renderer ..> Document : 依赖\n",
            ),
            "时序图": (
                "seq",
                "用户 -> 画布: 点击保存\n"
                "画布 -> Document: to_dict()\n"
                "Document --> 画布: 返回字典数据\n"
                "画布 -> Storage: save_json()\n"
                "Storage -> Storage: 序列化并写盘\n"
                "Storage --> 用户: 保存成功\n",
            ),
        }
        hints = {
            "甘特图": "每行一个任务：「名称: 起始周-结束周」或「名称, 起始周, 工期」；用「名称 @ 周」添加里程碑。",
            "UML 类图": "用「class 名称」声明类，「- 属性」「+ 方法」列成员，「A --> B : 标签」连关系，「A ..> B」为虚线依赖。",
            "时序图": "每行「发起者 -> 接收者: 文字」；「-->」表示返回（虚线）；首尾相同表示自调用。",
        }

        top = ttk.Frame(dialog, padding=(14, 12))
        top.pack(fill="x")
        ttk.Label(top, text="图表类型：").pack(side="left")
        type_var = tk.StringVar(value="甘特图")
        chooser = ttk.Combobox(top, textvariable=type_var, values=list(examples), state="readonly", width=14)
        chooser.pack(side="left", padx=(4, 0))

        hint_var = tk.StringVar()
        ttk.Label(dialog, textvariable=hint_var, wraplength=680, justify="left", foreground=THEME["subtext"]).pack(anchor="w", padx=14)

        editor = tk.Text(dialog, height=16, wrap="word", font=("Consolas", 11), undo=True)
        editor.pack(fill="both", expand=True, padx=14, pady=(6, 8))

        def load_example(*_args) -> None:
            editor.delete("1.0", "end")
            editor.insert("1.0", examples[type_var.get()][1])
            hint_var.set(hints[type_var.get()])

        chooser.bind("<<ComboboxSelected>>", load_example)
        load_example()

        def build_document() -> Document:
            source = editor.get("1.0", "end").strip()
            kind = examples[type_var.get()][0]
            if kind == "gantt":
                return parse_gantt_text(source, title="甘特图")
            if kind == "uml":
                return parse_uml_text(source, title="UML 类图")
            return parse_sequence_text(source, title="时序图")

        def generate(as_new_page: bool) -> None:
            try:
                document = build_document()
            except Exception as exc:
                messagebox.showerror("生成失败", str(exc), parent=dialog)
                return
            name = type_var.get()
            if as_new_page:
                self.add_page(document=document, name=name, status=f"已新建{name}页面")
            else:
                self._replace_current_document(document, status=f"已生成{name}", action=f"生成{name}")
            dialog.destroy()

        button_row = ttk.Frame(dialog, padding=(14, 8))
        button_row.pack(fill="x")
        ttk.Button(button_row, text="生成到新页面", command=lambda: generate(True)).pack(side="right", padx=4)
        ttk.Button(button_row, text="替换当前画布", command=lambda: generate(False)).pack(side="right", padx=4)
        ttk.Button(button_row, text="取消", command=dialog.destroy).pack(side="right", padx=4)

    def open_pages_window(self) -> None:
        if self._page_window and self._page_window.winfo_exists():
            self._page_window.lift()
            self._refresh_page_list()
            return

        window = tk.Toplevel(self.root)
        window.title("页面管理")
        window.geometry("360x460")
        window.transient(self.root)
        self._page_window = window

        ttk.Label(window, text="一个工程可包含多个页面，每页有独立的图形和历史。", wraplength=320, justify="left").pack(anchor="w", padx=14, pady=(14, 6))
        listbox = tk.Listbox(window, font=("Microsoft YaHei UI", 11), activestyle="dotbox")
        listbox.pack(fill="both", expand=True, padx=14, pady=4)
        self._page_listbox = listbox
        listbox.bind("<<ListboxSelect>>", lambda _event: self._on_page_list_select())
        listbox.bind("<Double-Button-1>", lambda _event: self.rename_page())

        controls = ttk.Frame(window, padding=(14, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="新建页面", command=self.add_page).pack(side="left", padx=3)
        ttk.Button(controls, text="重命名", command=self.rename_page).pack(side="left", padx=3)
        ttk.Button(controls, text="复制页面", command=self.duplicate_page).pack(side="left", padx=3)
        ttk.Button(controls, text="删除页面", command=self.delete_page).pack(side="left", padx=3)

        nav = ttk.Frame(window, padding=(14, 0))
        nav.pack(fill="x")
        ttk.Button(nav, text="上一页", command=self.prev_page).pack(side="left", padx=3)
        ttk.Button(nav, text="下一页", command=self.next_page).pack(side="left", padx=3)

        order = ttk.Frame(window, padding=(14, 0))
        order.pack(fill="x")
        ttk.Button(order, text="上移", command=lambda: self.move_page(-1)).pack(side="left", padx=3)
        ttk.Button(order, text="下移", command=lambda: self.move_page(1)).pack(side="left", padx=3)

        def close() -> None:
            if self._page_window is window:
                self._page_window = None
                self._page_listbox = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        self._refresh_page_list()

    def _refresh_page_list(self) -> None:
        if not self._page_listbox:
            return
        self._page_listbox.delete(0, "end")
        for index, page in enumerate(self.pages):
            self._page_listbox.insert("end", f"{index + 1}. {page['name']}  ({len(page['document'].shapes)} 个图元)")
        if 0 <= self.current_page_index < len(self.pages):
            self._page_listbox.selection_clear(0, "end")
            self._page_listbox.selection_set(self.current_page_index)
            self._page_listbox.activate(self.current_page_index)

    def _on_page_list_select(self) -> None:
        if not self._page_listbox:
            return
        selection = self._page_listbox.curselection()
        if not selection:
            return
        self.switch_page(selection[0])

    def _sync_current_page_document(self) -> None:
        if 0 <= self.current_page_index < len(self.pages):
            self.pages[self.current_page_index]["document"] = self.document
            self.pages[self.current_page_index]["history"] = self.history
            if self._page_window and self._page_window.winfo_exists():
                self._refresh_page_list()

    def _replace_current_document(self, document: Document, *, status: str, action: str) -> None:
        self.history.push(self.document)
        self.document = document
        self.selected_ids.clear()
        self.current_path = None
        self._sync_current_page_document()
        self.status_var.set(status)
        self._record_replay(action)
        self.redraw()

    def add_page(self, document: Document | None = None, name: str | None = None, status: str | None = None) -> None:
        self._sync_current_page_document()
        new_doc = document or Document()
        page_name = name or f"页面 {len(self.pages) + 1}"
        new_history = History()
        self.pages.append({"name": page_name, "document": new_doc, "history": new_history})
        self.current_page_index = len(self.pages) - 1
        self.document = new_doc
        self.history = new_history
        self.selected_ids.clear()
        self.replay_frames.clear()
        self.current_path = None
        self.status_var.set(status or f"已新建：{page_name}")
        self._record_replay(f"新建页面：{page_name}")
        self._refresh_page_list()
        self.redraw()

    def switch_page(self, index: int) -> None:
        if not self.pages:
            return
        index = max(0, min(len(self.pages) - 1, index))
        if index == self.current_page_index:
            return
        self._sync_current_page_document()
        self.current_page_index = index
        page = self.pages[index]
        self.document = page["document"]
        self.history = page["history"]
        self.selected_ids.clear()
        self.replay_frames.clear()
        self.current_path = None
        self.status_var.set(f"当前页面：{page['name']}")
        self._refresh_page_list()
        self.redraw()

    def prev_page(self) -> None:
        self.switch_page(self.current_page_index - 1)

    def next_page(self) -> None:
        self.switch_page(self.current_page_index + 1)

    def rename_page(self) -> None:
        if not self.pages:
            return
        current = self.pages[self.current_page_index]
        new_name = simpledialog.askstring("重命名页面", "页面名称：", initialvalue=current["name"], parent=self.root)
        if not new_name:
            return
        current["name"] = new_name.strip() or current["name"]
        self.status_var.set(f"已重命名：{current['name']}")
        self._refresh_page_list()

    def duplicate_page(self) -> None:
        if not self.pages:
            return
        self._sync_current_page_document()
        current = self.pages[self.current_page_index]
        clone_doc = current["document"].copy()
        clone_name = current["name"] + " 副本"
        self.add_page(document=clone_doc, name=clone_name, status=f"已复制为：{clone_name}")

    def delete_page(self) -> None:
        if len(self.pages) <= 1:
            messagebox.showinfo("无法删除", "至少需要保留一个页面。")
            return
        current = self.pages[self.current_page_index]
        if not messagebox.askyesno("删除页面", f"确认删除「{current['name']}」？此操作不可撤销。"):
            return
        self.pages.pop(self.current_page_index)
        self.current_page_index = max(0, min(self.current_page_index, len(self.pages) - 1))
        page = self.pages[self.current_page_index]
        self.document = page["document"]
        self.history = page["history"]
        self.selected_ids.clear()
        self.replay_frames.clear()
        self.status_var.set(f"已删除页面，当前：{page['name']}")
        self._refresh_page_list()
        self.redraw()

    def move_page(self, delta: int) -> None:
        target = self.current_page_index + delta
        if not (0 <= target < len(self.pages)):
            return
        self._sync_current_page_document()
        self.pages[self.current_page_index], self.pages[target] = self.pages[target], self.pages[self.current_page_index]
        self.current_page_index = target
        self._refresh_page_list()
        self.status_var.set("已调整页面顺序")

    def cancel_current(self) -> None:
        self.preview_shape = None
        self.connector_start_id = None
        self.marquee = None
        self.set_tool("select")
        self.redraw()
