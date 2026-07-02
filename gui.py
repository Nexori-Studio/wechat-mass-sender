# -*- coding: utf-8 -*-
"""
微信自动群发工具 - GUI
======================
深色专业风格图形界面，基于 tkinter + pyautogui 实现。

运行：python gui.py
"""

import os
import time
import threading
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime

from wechat_core import (
    DEFAULT_CONFIG,
    load_recipients,
    save_recipients,
    find_wechat_window,
    activate_wechat,
    send_with_retry,
    make_log_file,
    has_attachment,
    split_files,
    check_files_exist,
)

# ============================================================
# 主题：深色专业风（精美版）
# ============================================================

THEME = {
    "bg":              "#0d1117",
    "bg_elevated":     "#161b22",
    "bg_input":        "#21262d",
    "bg_hover":        "#30363d",
    "bg_pressed":      "#21262d",
    "bg_active":       "#1c2128",

    "fg":              "#f0f6fc",
    "fg_muted":        "#8b949e",
    "fg_subtle":       "#6e7681",
    "fg_success":      "#3fb950",
    "fg_warn":         "#d29922",
    "fg_error":        "#f85149",

    "border":          "#30363d",
    "border_focus":    "#58a6ff",
    "border_light":    "#3d4450",

    "accent":          "#58a6ff",
    "accent_hover":    "#79b8ff",
    "accent_active":   "#1f6feb",
    "accent_glow":     "#1f6feb",
    "accent_shadow":   "#161b22",
    "success":         "#3fb950",
    "success_hover":   "#56d364",
    "warn":            "#d29922",
    "warn_hover":      "#e3b341",
    "error":           "#f85149",
    "error_hover":     "#ff7b72",

    "log_bg":          "#010409",
    "log_fg":          "#c9d1d9",
    "log_success":     "#3fb950",
    "log_error":       "#f85149",
    "log_warn":        "#d29922",
    "log_highlight":   "#58a6ff",
}

APP_TITLE = "微信群发助手"
APP_W = 1040
APP_H = 820
RECIPIENTS_FILE = "recipients.csv"


# ============================================================
# 自定义控件：Toast 通知
# ============================================================

class Toast(tk.Toplevel):
    """轻量级通知弹窗，自动消失，不打断用户操作"""

    def __init__(self, parent, message, type="info", duration=3000):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(parent)
        self.configure(bg=THEME["bg_elevated"])

        types = {
            "info":   (THEME["accent"], "🔵"),
            "success":(THEME["success"], "✓"),
            "warn":   (THEME["warn"], "⚠️"),
            "error":  (THEME["error"], "✗"),
        }
        color, icon = types.get(type, types["info"])

        frame = tk.Frame(self, bg=THEME["bg_elevated"], padx=20, pady=14)
        frame.pack(fill="both")

        line = tk.Frame(frame, width=4, bg=color)
        line.pack(side="left", fill="y")

        icon_lbl = tk.Label(frame, text=icon, bg=THEME["bg_elevated"],
                            fg=color, font=("Segoe UI Emoji", 16), padx=12)
        icon_lbl.pack(side="left")

        text_lbl = tk.Label(frame, text=message, bg=THEME["bg_elevated"],
                            fg=THEME["fg"], font=("Microsoft YaHei", 11),
                            wraplength=320, justify="left")
        text_lbl.pack(side="left", fill="both")

        self.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        px = (parent.winfo_width() - pw) // 2
        py = parent.winfo_height() - ph - 50
        self.geometry(f"+{parent.winfo_x()+px}+{parent.winfo_y()+py}")

        self.deiconify()
        self.lift()
        self.after(duration, self.destroy)


# ============================================================
# 自定义控件：DarkButton 升级
# ============================================================

class DarkButton(tk.Canvas):
    """自绘按钮：支持悬停/按下/禁用/发光效果，圆角设计"""

    def __init__(self, parent, text, command=None, style="default", width=90, height=32, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=THEME["bg"], highlightthickness=0, bd=0, **kw)
        self._text = text
        self._command = command
        self._enabled = True
        self._style = style
        self._cw, self._ch = width, height
        self._pressed = False
        self._hover = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._render()

    def _colors(self):
        if not self._enabled:
            return THEME["bg_elevated"], THEME["fg_subtle"], THEME["border"], None
        if self._pressed:
            if self._style == "accent":
                return THEME["accent_active"], "#ffffff", THEME["accent_active"], THEME["accent_shadow"]
            if self._style == "danger":
                return THEME["error_hover"], "#ffffff", THEME["error_hover"], None
            if self._style == "success":
                return THEME["success"], "#0d1117", THEME["success"], None
            return THEME["bg_pressed"], THEME["fg"], THEME["border_light"], None
        if self._hover:
            if self._style == "accent":
                return THEME["accent_hover"], "#ffffff", THEME["accent_hover"], THEME["accent_glow"]
            if self._style == "danger":
                return THEME["error_hover"], "#ffffff", THEME["error_hover"], None
            if self._style == "success":
                return THEME["success_hover"], "#0d1117", THEME["success_hover"], None
            return THEME["bg_hover"], THEME["fg"], THEME["border_light"], None
        if self._style == "accent":
            return THEME["accent"], "#ffffff", THEME["accent"], THEME["accent_shadow"]
        if self._style == "danger":
            return THEME["error"], "#ffffff", THEME["error"], None
        if self._style == "success":
            return THEME["success"], "#0d1117", THEME["success"], None
        return THEME["bg_elevated"], THEME["fg"], THEME["border"], None

    def _render(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        bg, fg, border, glow = self._colors()
        r = 8
        x1, y1, x2, y2 = 0, 0, self._cw, self._ch

        if glow and self._hover:
            for i in range(3):
                rx1, ry1, rx2, ry2 = x1 - i, y1 - i, x2 + i, y2 + i
                rr = r + i
                alpha = 60 - i * 20
                points = [
                    rx1 + rr, ry1, rx2 - rr, ry1,
                    rx2 - rr, ry1, rx2, ry1, rx2, ry1 + rr,
                    rx2, ry1 + rr, rx2, ry2 - rr,
                    rx2, ry2 - rr, rx2, ry2, rx2 - rr, ry2,
                    rx2 - rr, ry2, rx1 + rr, ry2,
                    rx1 + rr, ry2, rx1, ry2, rx1, ry2 - rr,
                    rx1, ry2 - rr, rx1, ry1 + rr,
                    rx1, ry1 + rr, rx1, ry1, rx1 + rr, ry1,
                ]
                self.create_polygon(points, smooth=True, fill="", outline=glow, width=1)

        points = [
            x1 + r, y1, x2 - r, y1,
            x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y1 + r, x2, y2 - r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x2 - r, y2, x1 + r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1, x1 + r, y1,
        ]
        self.create_polygon(points, smooth=True, fill=bg, outline=border, width=2)

        offset_y = 1 if self._pressed else 0
        font_size = 10 if self._ch <= 32 else 11
        self.create_text(self._cw / 2, self._ch / 2 + offset_y, text=self._text,
                         fill=fg, font=("Microsoft YaHei", font_size, "bold"))

    def _on_enter(self, _):
        if not self._enabled:
            return
        self._hover = True
        self._render()

    def _on_leave(self, _):
        self._hover = False
        self._pressed = False
        try:
            self.configure(bg=THEME["bg"])
            self._render()
        except tk.TclError:
            pass

    def _on_press(self, _):
        if not self._enabled:
            return
        self._pressed = True
        self._render()

    def _on_release(self, _):
        if not self._enabled:
            return
        self._pressed = False
        self._render()
        if self._command:
            self._command()

    def configure_state(self, enabled):
        self._enabled = enabled
        try:
            self.configure(bg=THEME["bg"], cursor="hand2" if enabled else "arrow")
            self._render()
        except tk.TclError:
            pass


# ============================================================
# 自定义控件：其他
# ============================================================

class DarkEntry(tk.Entry):
    def __init__(self, parent, textvariable=None, width=10, **kw):
        super().__init__(parent, textvariable=textvariable, width=width,
                         bg=THEME["bg_input"], fg=THEME["fg"],
                         insertbackground=THEME["accent"],
                         relief="flat", bd=0, highlightthickness=2,
                         highlightcolor=THEME["border_focus"],
                         highlightbackground=THEME["border"],
                         font=("Consolas", 10), **kw)


class DarkText(scrolledtext.ScrolledText):
    def __init__(self, parent, **kw):
        super().__init__(parent,
                         bg=THEME["log_bg"], fg=THEME["log_fg"],
                         insertbackground=THEME["accent"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightcolor=THEME["border"],
                         highlightbackground=THEME["border"],
                         font=("Consolas", 10), wrap="word",
                         **kw)


class ProgressBar(tk.Canvas):
    """自绘进度条：带圆角和发光效果"""
    def __init__(self, parent, width=200, height=8, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=THEME["bg_elevated"], highlightthickness=0, bd=0, **kw)
        self._width = width
        self._height = height
        self._progress = 0.0
        self._render()

    def _render(self):
        self.delete("all")
        r = self._height // 2
        self.create_rounded_rect(0, 0, self._width, self._height, r,
                                 fill=THEME["bg_input"], outline="")
        if self._progress > 0:
            fill_w = int(self._width * self._progress)
            self.create_rounded_rect(0, 0, fill_w, self._height, r,
                                     fill=THEME["accent"], outline="")
            if fill_w > 10:
                self.create_rounded_rect(2, 2, fill_w - 2, self._height - 2, r - 1,
                                         fill=THEME["accent_hover"], outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1 + r, y1, x2 - r, y1,
            x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y1 + r, x2, y2 - r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x2 - r, y2, x1 + r, y2,
            x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1, x1 + r, y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)

    def set(self, value):
        self._progress = max(0.0, min(1.0, value))
        self._render()


# ============================================================
# 主题应用
# ============================================================

def apply_dark_theme(style):
    style.theme_use("clam")

    style.configure("Treeview",
                    background=THEME["bg_elevated"],
                    fieldbackground=THEME["bg_elevated"],
                    foreground=THEME["fg"],
                    borderwidth=0,
                    rowheight=34)
    style.configure("Treeview.Heading",
                    background=THEME["bg_input"],
                    foreground=THEME["fg_muted"],
                    relief="flat",
                    font=("Microsoft YaHei", 10, "bold"),
                    padding=8)
    style.map("Treeview",
              background=[("selected", THEME["accent"]), ("active", THEME["bg_hover"])],
              foreground=[("selected", "#ffffff"), ("active", THEME["fg"])])
    style.map("Treeview.Heading",
              background=[("active", THEME["bg_hover"])],
              foreground=[("active", THEME["fg"])])

    style.configure("TCombobox",
                    fieldbackground=THEME["bg_input"],
                    background=THEME["bg_input"],
                    foreground=THEME["fg"],
                    arrowcolor=THEME["fg_muted"],
                    relief="flat",
                    padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", THEME["bg_input"])],
              foreground=[("readonly", THEME["fg"])],
              selectbackground=[("readonly", THEME["bg_input"])],
              selectforeground=[("readonly", THEME["fg"])],
              arrowcolor=[("active", THEME["accent"])])

    style.configure("TFrame", background=THEME["bg"])
    style.configure("Card.TFrame", background=THEME["bg_elevated"])
    style.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 10))
    style.configure("Muted.TLabel", background=THEME["bg"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Card.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 10))
    style.configure("CardMuted.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Title.TLabel", background=THEME["bg"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 16, "bold"))
    style.configure("CardTitle.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 12, "bold"))
    style.configure("Status.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Hint.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_subtle"],
                    font=("Microsoft YaHei", 8))

    style.configure("TSeparator", background=THEME["border"])

    style.configure("Vertical.TScrollbar",
                    background=THEME["bg_input"],
                    troughcolor=THEME["bg_elevated"],
                    bordercolor=THEME["bg"],
                    arrowcolor=THEME["fg_muted"],
                    gripcount=0,
                    width=8)
    style.map("Vertical.TScrollbar",
              background=[("active", THEME["bg_hover"]), ("pressed", THEME["bg_pressed"])],
              arrowcolor=[("active", THEME["accent"])])

    style.configure("Horizontal.TScrollbar",
                    background=THEME["bg_input"],
                    troughcolor=THEME["bg_elevated"],
                    bordercolor=THEME["bg"],
                    arrowcolor=THEME["fg_muted"],
                    gripcount=0)
    style.map("Horizontal.TScrollbar",
              background=[("active", THEME["bg_hover"])],
              arrowcolor=[("active", THEME["accent"])])


# ============================================================
# 状态指示器
# ============================================================

class StatusIndicator(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=THEME["bg_elevated"], **kw)
        self._canvas = tk.Canvas(self, width=14, height=14,
                                 bg=THEME["bg_elevated"], highlightthickness=0, bd=0)
        self._canvas.pack(side="left", padx=(0, 10))
        self._dot = self._canvas.create_oval(3, 3, 11, 11, fill=THEME["fg_subtle"], outline="")
        self._pulse = None
        self._label = tk.Label(self, text="未连接", bg=THEME["bg_elevated"],
                               fg=THEME["fg_muted"], font=("Microsoft YaHei", 10))
        self._label.pack(side="left")

    def _start_pulse(self):
        self._stop_pulse()
        def pulse():
            try:
                alpha = (time.time() * 3) % 1
                color = f"#{int(0x3d + alpha*0x15):02x}{int(0x8b + alpha*0x09):02x}{int(0xf2 + alpha*0x03):02x}"
                self._canvas.itemconfig(self._dot, fill=color)
                self._pulse = self._canvas.after(50, pulse)
            except (tk.TclError, AttributeError):
                pass
        self._pulse = self._canvas.after(0, pulse)

    def _stop_pulse(self):
        if self._pulse:
            try:
                self._canvas.after_cancel(self._pulse)
            except (tk.TclError, AttributeError):
                pass
            self._pulse = None

    def set_state(self, state):
        self._stop_pulse()
        states = {
            "idle":    (THEME["fg_subtle"], "未连接"),
            "ready":   (THEME["success"], "微信已就绪"),
            "running": (THEME["warn"], "发送中..."),
            "error":   (THEME["error"], "异常"),
        }
        color, text = states.get(state, states["idle"])
        self._canvas.itemconfig(self._dot, fill=color)
        self._label.configure(text=text)
        if state == "running":
            self._start_pulse()


# ============================================================
# 主应用
# ============================================================

class MassSenderApp:

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        icon_path = os.path.join(os.path.dirname(__file__), "wechat_icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(APP_W, screen_w - 80)
        win_h = min(APP_H, screen_h - 120)
        x = (screen_w - win_w) // 2
        y = max(0, (screen_h - win_h) // 2 - 20)
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.minsize(920, 700)
        self.root.configure(bg=THEME["bg"])

        self.recipients = []
        self.config = dict(DEFAULT_CONFIG)
        self.sending = False
        self.stop_flag = False
        self._log_file = make_log_file()

        self._build_style()
        self._build_ui()
        self._load_data()
        self._check_wechat_status()
        self.root.after(2000, self._check_wechat_status)

    def _build_style(self):
        self.style = ttk.Style()
        apply_dark_theme(self.style)

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        header = ttk.Frame(self.root, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 8))

        inner = ttk.Frame(header, style="Card.TFrame")
        inner.pack(fill="x", padx=16, pady=14)

        title_box = ttk.Frame(inner, style="Card.TFrame")
        title_box.pack(side="left")

        icon_label = tk.Label(title_box, text="💬", bg=THEME["bg_elevated"],
                              font=("Segoe UI Emoji", 24))
        icon_label.pack(side="left", padx=(0, 12))

        title_box2 = ttk.Frame(title_box, style="Card.TFrame")
        title_box2.pack(side="left")

        title_lbl = ttk.Label(title_box2, text=APP_TITLE, style="Title.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(title_box2, text="微信 PC 版自动群发工具", style="CardMuted.TLabel")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        self.indicator = StatusIndicator(inner)
        self.indicator.pack(side="right", padx=(0, 12))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=12)

        # 主区域
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=20, pady=12)

        # 左侧：收件人卡片
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._build_recipients_card(left)

        # 右侧：配置 + 日志
        right = ttk.Frame(main)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))
        self._build_config_card(right)
        self._build_log_card(right)

        # 底部状态栏
        self._build_status_bar()

    def _build_recipients_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)

        title_bar = ttk.Frame(card, style="Card.TFrame")
        title_bar.pack(fill="x", pady=(0, 12))

        ttk.Label(title_bar, text="收件人", style="CardTitle.TLabel").pack(side="left")

        btn_box = ttk.Frame(title_bar, style="Card.TFrame")
        btn_box.pack(side="right")

        self.btn_add = DarkButton(btn_box, "➕ 添加", command=self.add_recipient, width=80, height=28)
        self.btn_add.pack(side="left", padx=2)
        self.btn_batch = DarkButton(btn_box, "📋 批量", command=self.batch_add, width=80, height=28)
        self.btn_batch.pack(side="left", padx=2)
        self.btn_edit = DarkButton(btn_box, "✏️ 编辑", command=self.edit_recipient, width=80, height=28)
        self.btn_edit.pack(side="left", padx=2)
        self.btn_del = DarkButton(btn_box, "🗑 删除", command=self.delete_recipient, width=80, height=28)
        self.btn_del.pack(side="left", padx=2)

        table_frame = ttk.Frame(card, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "type", "message", "file")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="名称", anchor="w")
        self.tree.heading("type", text="类型", anchor="center")
        self.tree.heading("message", text="消息模板", anchor="w")
        self.tree.heading("file", text="附件", anchor="center")
        self.tree.column("name", width=140, anchor="w", stretch=False)
        self.tree.column("type", width=70, anchor="center", stretch=False)
        self.tree.column("message", width=260, anchor="w")
        self.tree.column("file", width=70, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview,
                            style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("oddrow", background=THEME["bg_elevated"])
        self.tree.tag_configure("evenrow", background="#262b34")

        self.tree.bind("<Double-1>", lambda e: self.edit_recipient())

        bottom = ttk.Frame(card, style="Card.TFrame")
        bottom.pack(fill="x", pady=(10, 0))

        self.var_status = tk.StringVar(value="共 0 位收件人")
        ttk.Label(bottom, textvariable=self.var_status, style="CardMuted.TLabel").pack(side="left")

        DarkButton(bottom, "📂 导入", command=self.import_csv, width=72, height=28).pack(side="right", padx=2)
        DarkButton(bottom, "💾 保存", command=self.save_data, width=72, height=28).pack(side="right", padx=2)

    def _build_config_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(0, 12))

        ttk.Label(card, text="发送配置", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))

        row1 = ttk.Frame(card, style="Card.TFrame")
        row1.pack(fill="x", pady=4)
        self._labeled_entry(row1, "最小延时(秒)", "var_min_delay", str(self.config["min_delay"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row1, "最大延时(秒)", "var_max_delay", str(self.config["max_delay"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row1, "重试次数", "var_max_retries", str(self.config["max_retries"]), width=4).pack(side="left", padx=(0, 16))

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=4)
        self._labeled_entry(row2, "点击 X 比例", "var_click_x", str(self.config["click_x_ratio"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row2, "点击 Y 比例", "var_click_y", str(self.config["click_y_ratio"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row2, "搜索等待(秒)", "var_search_wait", str(self.config["search_wait"])).pack(side="left", padx=(0, 16))

        action_bar = ttk.Frame(card, style="Card.TFrame")
        action_bar.pack(fill="x", pady=(14, 0))

        ttk.Label(action_bar, text="💡 紧急停止：将鼠标快速移到屏幕左上角",
                  style="Hint.TLabel").pack(side="left")

        self.btn_stop = DarkButton(action_bar, "⏹ 停止", command=self.stop_send,
                                   style="danger", width=90, height=32)
        self.btn_stop.pack(side="right", padx=(8, 0))
        self.btn_stop.configure_state(False)

        self.btn_send = DarkButton(action_bar, "🚀 开始群发", command=self.start_send,
                                   style="accent", width=120, height=32)
        self.btn_send.pack(side="right")

    def _labeled_entry(self, parent, label, var_name, default, width=8):
        box = ttk.Frame(parent, style="Card.TFrame")
        ttk.Label(box, text=label, style="CardMuted.TLabel").pack(side="left", padx=(0, 6))
        var = tk.StringVar(value=default)
        setattr(self, var_name, var)
        DarkEntry(box, textvariable=var, width=width).pack(side="left")
        return box

    def _build_log_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)

        title_bar = ttk.Frame(card, style="Card.TFrame")
        title_bar.pack(fill="x", pady=(0, 8))

        ttk.Label(title_bar, text="运行日志", style="CardTitle.TLabel").pack(side="left")

        self.var_count = tk.StringVar(value="")
        ttk.Label(title_bar, textvariable=self.var_count, style="CardMuted.TLabel").pack(side="right")

        self.log_text = DarkText(card, height=10)
        self.log_text.pack(fill="both", expand=True, pady=(0, 8))

        self.log_text.tag_configure("info", foreground=THEME["log_fg"])
        self.log_text.tag_configure("success", foreground=THEME["log_success"])
        self.log_text.tag_configure("error", foreground=THEME["log_error"])
        self.log_text.tag_configure("warn", foreground=THEME["log_warn"])
        self.log_text.tag_configure("highlight", foreground=THEME["log_highlight"])

        # 进度条
        progress_box = ttk.Frame(card, style="Card.TFrame")
        progress_box.pack(fill="x")

        self.progress_bar = ProgressBar(progress_box, width=300, height=6)
        self.progress_bar.pack(side="left", padx=(0, 10))

        self.var_progress = tk.StringVar(value="0%")
        ttk.Label(progress_box, textvariable=self.var_progress, style="CardMuted.TLabel").pack(side="left")

    def _build_status_bar(self):
        self.status_bar = ttk.Frame(self.root, style="Card.TFrame", padding=(16, 8))
        self.status_bar.pack(fill="x", padx=12, pady=(0, 12))

        left_box = ttk.Frame(self.status_bar, style="Card.TFrame")
        left_box.pack(side="left")

        self.var_status_text = tk.StringVar(value="就绪")
        ttk.Label(left_box, textvariable=self.var_status_text, style="CardMuted.TLabel").pack(side="left")

        ttk.Separator(left_box, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Label(left_box, text="微信 PC 版", style="CardMuted.TLabel").pack(side="left", padx=(0, 12))

        right_box = ttk.Frame(self.status_bar, style="Card.TFrame")
        right_box.pack(side="right")

        ttk.Label(right_box, text="v1.0", style="CardMuted.TLabel").pack(side="right")

    # ---------------- 数据 ----------------

    def _load_data(self):
        self.recipients = load_recipients(RECIPIENTS_FILE)
        self._refresh_tree()
        self._log("欢迎使用微信自动群发工具", "highlight")
        self._log(f"数据源: {RECIPIENTS_FILE}", "info")

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        type_map = {"contact": "联系人", "group": "群聊"}
        for i, r in enumerate(self.recipients):
            tag = "oddrow" if i % 2 == 0 else "evenrow"
            attachments = split_files(r.get("file", ""))
            if attachments:
                if len(attachments) == 1:
                    ext = os.path.splitext(attachments[0])[1].lower()
                    file_disp = f"📎{ext or '📄'}"
                else:
                    file_disp = f"📎x{len(attachments)}"
            else:
                file_disp = "—"
            self.tree.insert("", "end", values=(
                r["name"],
                type_map.get(r["type"], r["type"]),
                r.get("message", ""),
                file_disp,
            ), tags=(tag,))
        self.var_status.set(f"共 {len(self.recipients)} 位收件人")

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return -1
        return self.tree.index(sel[0])

    def save_data(self):
        try:
            save_recipients(RECIPIENTS_FILE, self.recipients)
            self._log(f"已保存 {len(self.recipients)} 条记录", "success")
            Toast(self.root, "保存成功", "success")
        except Exception as e:
            Toast(self.root, f"保存失败: {e}", "error")

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="选择 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            data = load_recipients(path)
            if not data:
                Toast(self.root, "文件中没有有效数据", "warn")
                return
            if messagebox.askyesno("确认", f"读取到 {len(data)} 条记录，是否替换当前列表？"):
                self.recipients = data
                self._refresh_tree()
                self._log(f"已导入 {len(data)} 条记录", "success")
                Toast(self.root, f"已导入 {len(data)} 条记录", "success")
        except Exception as e:
            Toast(self.root, f"导入失败: {e}", "error")

    # ---------------- 增删改 ----------------

    def add_recipient(self):
        self._open_editor(None)

    def batch_add(self):
        """打开批量添加弹窗"""
        self._open_batch_editor()

    def edit_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            Toast(self.root, "请先选择一条记录", "warn")
            return
        self._open_editor(idx)

    def delete_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            Toast(self.root, "请先选择一条记录", "warn")
            return
        name = self.recipients[idx]["name"]
        if messagebox.askyesno("确认删除", f"确定删除「{name}」吗？"):
            del self.recipients[idx]
            self._refresh_tree()
            Toast(self.root, "已删除", "info")

    def _open_editor(self, idx):
        is_edit = idx is not None
        win = tk.Toplevel(self.root)
        win.title("编辑收件人" if is_edit else "添加收件人")
        win.geometry("560x560")
        win.resizable(False, False)
        win.configure(bg=THEME["bg"])
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="名称").grid(row=0, column=0, sticky="w", pady=6)
        var_name = tk.StringVar(value=self.recipients[idx]["name"] if is_edit else "")
        DarkEntry(outer, textvariable=var_name, width=36).grid(row=0, column=1, sticky="we", pady=6, padx=(12, 0))

        ttk.Label(outer, text="类型").grid(row=1, column=0, sticky="w", pady=6)
        var_type = tk.StringVar(value=self.recipients[idx].get("type", "contact") if is_edit else "contact")
        type_combo = ttk.Combobox(outer, textvariable=var_type, state="readonly", width=12,
                                  values=["contact", "group"])
        type_combo.grid(row=1, column=1, sticky="w", pady=6, padx=(12, 0))

        ttk.Label(outer, text="消息模板").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        msg_box = ttk.Frame(outer)
        msg_box.grid(row=2, column=1, sticky="we", pady=6, padx=(12, 0))
        msg_text = DarkText(msg_box, width=42, height=6)
        msg_text.pack(fill="both", expand=True)
        if is_edit:
            msg_text.insert("1.0", self.recipients[idx].get("message", ""))

        ttk.Label(outer, text="💡 可用 {name} 作为名称占位符",
                  style="Muted.TLabel").grid(row=3, column=1, sticky="w", pady=(4, 0))

        # 附件管理
        ttk.Label(outer, text="附件").grid(row=4, column=0, sticky="nw", pady=(8, 0))
        file_box = ttk.Frame(outer, style="Card.TFrame", padding=8)
        file_box.grid(row=4, column=1, sticky="we", pady=(8, 0), padx=(12, 0))

        # 文件列表展示
        files_var = tk.StringVar(value="")
        if is_edit:
            files_var.set(self.recipients[idx].get("file", ""))
        files_list_frame = ttk.Frame(file_box, style="Card.TFrame")
        files_list_frame.pack(fill="x")

        files_display_var = tk.StringVar(value="")
        files_count_var = tk.StringVar(value="")

        def refresh_files_display():
            paths = split_files(files_var.get())
            if not paths:
                files_display_var.set("(无附件)")
                files_count_var.set("")
            else:
                files_display_var.set("\n".join(f"  • {os.path.basename(p)}" for p in paths))
                files_count_var.set(f"共 {len(paths)} 个")

        files_count_lbl = tk.Label(files_list_frame, textvariable=files_count_var,
                                   bg=THEME["bg_elevated"], fg=THEME["accent"],
                                   font=("Microsoft YaHei", 9, "bold"))
        files_count_lbl.pack(side="top", anchor="e")
        files_text = tk.Label(files_list_frame, textvariable=files_display_var,
                              bg=THEME["bg_elevated"], fg=THEME["fg_muted"],
                              font=("Consolas", 9), justify="left", anchor="w",
                              wraplength=360, height=4)
        files_text.pack(side="top", fill="x", pady=(2, 6))

        # 按钮行
        file_btn_row = ttk.Frame(file_box, style="Card.TFrame")
        file_btn_row.pack(fill="x")

        def pick_files():
            paths = filedialog.askopenfilenames(
                title="选择文件（可多选）",
                filetypes=[
                    ("所有文件", "*.*"),
                    ("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                    ("文档", "*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt"),
                ],
            )
            if not paths:
                return
            existing = split_files(files_var.get())
            new_all = existing + list(paths)
            files_var.set("|".join(new_all))
            refresh_files_display()

        def clear_files():
            files_var.set("")
            refresh_files_display()

        DarkButton(file_btn_row, "📁 选择文件", command=pick_files,
                   style="accent", width=110, height=28).pack(side="left", padx=2)
        DarkButton(file_btn_row, "🗑 清空附件", command=clear_files,
                   width=110, height=28).pack(side="left", padx=2)

        ttk.Label(file_box, text="💡 支持多文件，用 | 分隔；图片/文件均可发送",
                  style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        refresh_files_display()

        # 预览
        ttk.Label(outer, text="预览").grid(row=5, column=0, sticky="nw", pady=(8, 0))
        preview_var = tk.StringVar(value="")
        preview_box = ttk.Frame(outer, style="Card.TFrame", padding=10)
        preview_box.grid(row=5, column=1, sticky="we", pady=(8, 0), padx=(12, 0))
        preview_lbl = tk.Label(preview_box, textvariable=preview_var,
                               bg=THEME["bg_elevated"], fg=THEME["accent"],
                               font=("Microsoft YaHei", 10), wraplength=380,
                               justify="left", anchor="w")
        preview_lbl.pack(fill="x")

        def update_preview(*_):
            name = var_name.get().strip() or "{name}"
            msg = msg_text.get("1.0", "end-1c")
            preview_var.set(msg.replace("{name}", name)[:200])

        var_name.trace_add("write", update_preview)
        msg_text.bind("<KeyRelease>", lambda e: update_preview())
        update_preview()

        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))

        def on_save():
            name = var_name.get().strip()
            rtype = var_type.get().strip() or "contact"
            message = msg_text.get("1.0", "end-1c")
            files = files_var.get().strip()
            if not name:
                Toast(win, "名称不能为空", "error")
                return
            data = {"name": name, "type": rtype, "message": message, "file": files}
            if is_edit:
                self.recipients[idx] = data
            else:
                self.recipients.append(data)
            self._refresh_tree()
            Toast(self.root, "保存成功", "success")
            win.destroy()

        DarkButton(btn_frame, "保存", command=on_save, style="accent", width=90, height=32).pack(side="right", padx=4)
        DarkButton(btn_frame, "取消", command=win.destroy, width=90, height=32).pack(side="right", padx=4)

    def _open_batch_editor(self):
        """批量添加弹窗：
        上方：选择文件/图片（应用到全部收件人）
        下方：表格批量输入收件人（每行：类型 + 名称 + 消息）
        """
        win = tk.Toplevel(self.root)
        win.title("批量添加收件人")
        win.geometry("780x600")
        win.configure(bg=THEME["bg"])
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=14)
        outer.pack(fill="both", expand=True)

        # 顶部：通用附件设置
        top_box = ttk.Frame(outer, style="Card.TFrame", padding=10)
        top_box.pack(fill="x", pady=(0, 10))

        ttk.Label(top_box, text="统一附件（可选）", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))

        batch_files_var = tk.StringVar(value="")
        batch_files_display = tk.StringVar(value="(无附件)")
        batch_files_count = tk.StringVar(value="")

        def refresh_batch_files():
            paths = split_files(batch_files_var.get())
            if not paths:
                batch_files_display.set("(无附件)")
                batch_files_count.set("")
            else:
                batch_files_display.set("  • ".join(os.path.basename(p) for p in paths))
                batch_files_count.set(f"共 {len(paths)} 个")

        def pick_batch_files():
            paths = filedialog.askopenfilenames(
                title="选择文件（可多选，应用于所有收件人）",
                filetypes=[
                    ("所有文件", "*.*"),
                    ("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                    ("文档", "*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt"),
                ],
            )
            if not paths:
                return
            existing = split_files(batch_files_var.get())
            new_all = existing + list(paths)
            batch_files_var.set("|".join(new_all))
            refresh_batch_files()

        def clear_batch_files():
            batch_files_var.set("")
            refresh_batch_files()

        info_row = ttk.Frame(top_box, style="Card.TFrame")
        info_row.pack(fill="x")

        count_lbl = tk.Label(info_row, textvariable=batch_files_count,
                             bg=THEME["bg_elevated"], fg=THEME["accent"],
                             font=("Microsoft YaHei", 9, "bold"))
        count_lbl.pack(side="right")
        files_lbl = tk.Label(info_row, textvariable=batch_files_display,
                             bg=THEME["bg_elevated"], fg=THEME["fg_muted"],
                             font=("Consolas", 9), anchor="w")
        files_lbl.pack(side="left", fill="x", expand=True)

        btn_row = ttk.Frame(top_box, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(6, 0))
        DarkButton(btn_row, "📁 选择文件", command=pick_batch_files,
                   style="accent", width=110, height=28).pack(side="left", padx=2)
        DarkButton(btn_row, "🗑 清空", command=clear_batch_files,
                   width=80, height=28).pack(side="left", padx=2)
        ttk.Label(btn_row, text="💡 选中的文件/图片将作为附件，发送给下方所有收件人",
                  style="Hint.TLabel").pack(side="left", padx=10)

        # 中间：批量输入表格
        mid_box = ttk.Frame(outer, style="Card.TFrame", padding=10)
        mid_box.pack(fill="both", expand=True)

        ttk.Label(mid_box, text="收件人列表（每行一个）", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))

        # 通用消息模板
        ttk.Label(mid_box, text="通用消息模板:", style="CardMuted.TLabel").pack(anchor="w")
        batch_msg_text = DarkText(mid_box, height=4)
        batch_msg_text.pack(fill="x", pady=(2, 8))
        batch_msg_text.insert("1.0", "你好 {name}，这是一条群发消息。")

        # 表格
        columns = ("type", "name")
        batch_tree = ttk.Treeview(mid_box, columns=columns, show="headings", height=8)
        batch_tree.heading("type", text="类型", anchor="center")
        batch_tree.heading("name", text="名称", anchor="w")
        batch_tree.column("type", width=80, anchor="center", stretch=False)
        batch_tree.column("name", width=580, anchor="w")

        # 预填 3 行
        for _ in range(3):
            batch_tree.insert("", "end", values=("contact", ""))

        vsb = ttk.Scrollbar(mid_box, orient="vertical", command=batch_tree.yview,
                            style="Vertical.TScrollbar")
        batch_tree.configure(yscrollcommand=vsb.set)
        batch_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 类型双击切换
        def on_double_click(event):
            item = batch_tree.identify_row(event.y)
            if not item:
                return
            col = batch_tree.identify_column(event.x)
            if col == "#1":  # 类型列
                vals = list(batch_tree.item(item, "values"))
                vals[0] = "group" if vals[0] == "contact" else "contact"
                batch_tree.item(item, values=vals)

        batch_tree.bind("<Double-1>", on_double_click)

        # 表格按钮
        tree_btn_row = ttk.Frame(outer)
        tree_btn_row.pack(fill="x", pady=(8, 0))

        def add_row():
            batch_tree.insert("", "end", values=("contact", ""))

        def del_row():
            sel = batch_tree.selection()
            for item in sel:
                batch_tree.delete(item)

        def batch_import():
            """从剪贴板批量导入（每行一个名称）"""
            try:
                import pyperclip
                text = pyperclip.paste()
                if not text:
                    Toast(win, "剪贴板为空", "warn")
                    return
                # 清掉现有空行
                for item in batch_tree.get_children():
                    vals = batch_tree.item(item, "values")
                    if not vals[1].strip():
                        batch_tree.delete(item)
                # 添加
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines:
                    # 自动判断类型
                    rtype = "group" if (line.endswith("群") or line.endswith("Group")) else "contact"
                    batch_tree.insert("", "end", values=(rtype, line))
                Toast(win, f"从剪贴板导入 {len(lines)} 条", "success")
            except Exception as e:
                Toast(win, f"导入失败: {e}", "error")

        DarkButton(tree_btn_row, "➕ 加行", command=add_row,
                   width=80, height=28).pack(side="left", padx=2)
        DarkButton(tree_btn_row, "➖ 删行", command=del_row,
                   width=80, height=28).pack(side="left", padx=2)
        DarkButton(tree_btn_row, "📋 从剪贴板导入", command=batch_import,
                   style="accent", width=140, height=28).pack(side="left", padx=2)
        ttk.Label(tree_btn_row, text="💡 双击类型列切换 联系人/群聊",
                  style="Hint.TLabel").pack(side="left", padx=10)

        # 底部：保存/取消
        bottom_btn_row = ttk.Frame(outer)
        bottom_btn_row.pack(fill="x", pady=(14, 0))

        def on_batch_save():
            template = batch_msg_text.get("1.0", "end-1c")
            files = batch_files_var.get().strip()
            added = 0
            skipped = 0
            for item in batch_tree.get_children():
                vals = batch_tree.item(item, "values")
                rtype, name = vals[0], vals[1].strip()
                if not name:
                    continue
                self.recipients.append({
                    "name": name,
                    "type": rtype if rtype in ("contact", "group") else "contact",
                    "message": template,
                    "file": files,
                })
                added += 1
            self._refresh_tree()
            if added:
                Toast(self.root, f"已添加 {added} 位收件人", "success")
            else:
                Toast(self.root, "未添加任何收件人", "warn")
            win.destroy()

        DarkButton(bottom_btn_row, "保存", command=on_batch_save,
                   style="accent", width=120, height=32).pack(side="right", padx=4)
        DarkButton(bottom_btn_row, "取消", command=win.destroy,
                   width=90, height=32).pack(side="right", padx=4)

    # ---------------- 状态检查 ----------------

    def _check_wechat_status(self):
        if self.sending:
            self.indicator.set_state("running")
        else:
            hwnd, _ = find_wechat_window()
            self.indicator.set_state("ready" if hwnd else "idle")
        self.root.after(2000, self._check_wechat_status)

    # ---------------- 日志 ----------------

    def _log(self, msg, tag="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line, tag)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        try:
            self.root.after(0, _append)
        except RuntimeError:
            pass

    # ---------------- 发送 ----------------

    def _collect_config(self):
        try:
            cfg = {
                "min_delay": float(self.var_min_delay.get()),
                "max_delay": float(self.var_max_delay.get()),
                "step_delay": DEFAULT_CONFIG["step_delay"],
                "search_wait": float(self.var_search_wait.get()),
                "max_retries": int(self.var_max_retries.get()),
                "click_x_ratio": float(self.var_click_x.get()),
                "click_y_ratio": float(self.var_click_y.get()),
            }
            if cfg["min_delay"] > cfg["max_delay"]:
                cfg["min_delay"], cfg["max_delay"] = cfg["max_delay"], cfg["min_delay"]
            return cfg
        except (ValueError, AttributeError) as e:
            Toast(self.root, f"配置错误: {e}", "error")
            return None

    def _update_progress(self, current, total):
        try:
            percent = int((current / total) * 100) if total > 0 else 0
            self.root.after(0, lambda: self.progress_bar.set(current / total))
            self.root.after(0, lambda: self.var_progress.set(f"{percent}%"))
            self.root.after(0, lambda: self.var_status_text.set(f"发送中 {current}/{total}"))
        except (RuntimeError, AttributeError):
            pass

    def start_send(self):
        if self.sending:
            return
        if not self.recipients:
            Toast(self.root, "收件人列表为空", "warn")
            return

        config = self._collect_config()
        if config is None:
            return

        # 校验附件存在性
        missing_total = []
        for r in self.recipients:
            ok, missing = check_files_exist(r)
            if not ok:
                for m in missing:
                    missing_total.append(f"{r['name']}: {os.path.basename(m)}")
        if missing_total:
            sample = "\n".join(missing_total[:5])
            more = f"\n\n...还有 {len(missing_total)-5} 个" if len(missing_total) > 5 else ""
            if not messagebox.askyesno("附件缺失",
                                       f"以下附件文件不存在，将无法发送：\n\n{sample}{more}\n\n"
                                       f"是否仍要继续发送（失败的附件会被跳过）？"):
                return

        hwnd, _ = find_wechat_window()
        if not hwnd:
            Toast(self.root, "未找到微信窗口", "error")
            return

        count = len(self.recipients)
        if not messagebox.askyesno("确认发送",
                                   f"即将向 {count} 位收件人发送消息。\n\n"
                                   f"发送过程中请勿操作鼠标键盘。\n"
                                   f"紧急停止：将鼠标移到屏幕左上角。\n\n"
                                   f"确认开始吗？"):
            return

        self.save_data()

        self.sending = True
        self.stop_flag = False
        self.btn_send.configure_state(False)
        self.btn_stop.configure_state(True)
        self.indicator.set_state("running")
        self.progress_bar.set(0)
        self.var_progress.set("0%")

        self._log(f"开始群发，共 {count} 位收件人", "highlight")

        if not activate_wechat(lambda m: self._log(m, "info")):
            self._log("预检失败：无法激活微信窗口，已中止", "error")
            self._finish_send()
            Toast(self.root, "无法激活微信窗口", "error")
            return

        for i in range(3, 0, -1):
            self._log(f"{i} 秒后开始发送...", "warn")
            self.root.update()
            time.sleep(1)

        t = threading.Thread(target=self._send_worker, args=(config,), daemon=True)
        t.start()

    def stop_send(self):
        if self.sending:
            self.stop_flag = True
            self._log("正在停止...", "warn")
            Toast(self.root, "正在停止发送", "warn")

    def _send_worker(self, config):
        total = len(self.recipients)
        success, failed = [], []

        for idx, r in enumerate(self.recipients, start=1):
            if self.stop_flag:
                self._log("已手动停止", "warn")
                break

            self._update_progress(idx - 1, total)

            tag = "群聊" if r["type"] == "group" else "联系人"
            self._log(f"({idx}/{total}) [{tag}] {r['name']} ...", "info")

            ok, info = send_with_retry(r, config, lambda m: self._log(m, "info"))
            if ok:
                self._log(f"  ✓ {info}", "success")
                success.append(r["name"])
            else:
                self._log(f"  ✗ {info}", "error")
                failed.append((r["name"], info))
                if "紧急停止" in info:
                    self._log("检测到紧急停止信号，终止群发。", "error")
                    break

            if idx < total and not self.stop_flag:
                delay = random.uniform(config.get("min_delay", 5.0), config.get("max_delay", 12.0))
                time.sleep(delay)

        self._update_progress(total, total)

        self._log("=" * 40, "highlight")
        self._log(f"完成：成功 {len(success)} / 失败 {len(failed)} / 共 {total}", "highlight")
        if failed:
            self._log("失败列表：", "warn")
            for name, info in failed:
                self._log(f"  - {name}: {info}", "error")

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"\n完成：成功 {len(success)} / 失败 {len(failed)} / 共 {total}\n")
                for name, info in failed:
                    f.write(f"  - {name}: {info}\n")
        except Exception:
            pass

        self.var_count.set(f"本次: 成功 {len(success)} / 失败 {len(failed)}")
        Toast(self.root, f"发送完成！成功 {len(success)} / 失败 {len(failed)}",
              "success" if not failed else "warn")

        self._finish_send()

    def _finish_send(self):
        def _update():
            self.sending = False
            self.stop_flag = False
            self.btn_send.configure_state(True)
            self.btn_stop.configure_state(False)
            self.var_status_text.set("就绪")
            hwnd, _ = find_wechat_window()
            self.indicator.set_state("ready" if hwnd else "idle")

        self.root.after(0, _update)


def main():
    root = tk.Tk()
    app = MassSenderApp(root)
    app._log("请确认微信已登录并保持窗口可见", "info")
    root.mainloop()


if __name__ == "__main__":
    main()
