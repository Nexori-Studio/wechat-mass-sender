# -*- coding: utf-8 -*-
"""
Prism — 微信自动群发工具
========================
白色天蓝主题，侧边栏布局，基于 tkinter + pyautogui 实现。

运行：python gui.py
"""

import os
import sys
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
    parse_schedule,
)

# ============================================================
# 内置消息模板库
# ============================================================

MESSAGE_TEMPLATES = {
    "通用问候": [
        "你好 {name}，祝你一切顺利！",
        "Hi {name}，最近怎么样？",
        "{name} 好呀，问候一下~",
    ],
    "节日祝福": [
        "🎉 祝 {name} 节日快乐，万事如意！",
        "🌸 {name}，愿你每一天都开心！",
        "🎊 {name}，恭祝你心想事成！",
    ],
    "商务合作": [
        "{name} 您好，关于我们的合作，期待与您进一步沟通。",
        "{name} 您好，附件是相关资料，请查阅。",
        "尊敬的 {name}，感谢您的关注与支持！",
    ],
    "客户回访": [
        "{name} 您好，近期使用是否顺利？有什么问题随时联系我。",
        "{name}，感谢您一直以来的支持！",
        "{name}，温馨提醒：您的会员即将到期，欢迎续费~",
    ],
    "活动通知": [
        "🎁 {name}，我们最新活动开始啦，点击查看详情！",
        "{name}，限时优惠等你来抢，错过等一年！",
        "📢 {name}，新功能上线，立即体验！",
    ],
    "自定义": [""],
}

# ============================================================
# 主题：白色 + 天蓝
# ============================================================

THEME = {
    "bg":              "#f5f7fa",
    "bg_elevated":     "#ffffff",
    "bg_input":        "#ffffff",
    "bg_hover":        "#f0f4ff",
    "bg_pressed":      "#e8f0fe",
    "bg_active":       "#f0f7ff",

    "fg":              "#1e293b",
    "fg_muted":        "#64748b",
    "fg_subtle":       "#94a3b8",
    "fg_success":      "#10b981",
    "fg_warn":         "#f59e0b",
    "fg_error":        "#ef4444",

    "border":          "#e2e8f0",
    "border_focus":    "#0ea5e9",
    "border_light":    "#f1f5f9",

    "accent":          "#0ea5e9",
    "accent_hover":    "#38bdf8",
    "accent_active":   "#0284c7",
    "accent_glow":     "#bae6fd",
    "accent_shadow":   "#e0f2fe",
    "success":         "#10b981",
    "success_hover":   "#34d399",
    "warn":            "#f59e0b",
    "warn_hover":      "#fbbf24",
    "error":           "#ef4444",
    "error_hover":     "#f87171",

    "sidebar_bg":      "#ffffff",
    "sidebar_border":  "#e2e8f0",
    "sidebar_active":  "#e0f2fe",

    "log_bg":          "#ffffff",
    "log_fg":          "#334155",
    "log_success":     "#10b981",
    "log_error":       "#ef4444",
    "log_warn":        "#f59e0b",
    "log_highlight":   "#0ea5e9",
}

APP_TITLE = "Prism"
APP_W = 1600
APP_H = 900
RECIPIENTS_FILE = "recipients.csv"
SIDEBAR_W = 220


# ============================================================
# Toast 通知
# ============================================================

class Toast(tk.Toplevel):
    def __init__(self, parent, message, msg_type="info", duration=3000):
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
        color, icon = types.get(msg_type, types["info"])

        frame = tk.Frame(self, bg=THEME["bg_elevated"], padx=20, pady=14)
        frame.pack(fill="both")

        line = tk.Frame(frame, width=4, bg=color)
        line.pack(side="left", fill="y")

        tk.Label(frame, text=icon, bg=THEME["bg_elevated"], fg=color,
                 font=("Segoe UI Emoji", 16), padx=12).pack(side="left")
        tk.Label(frame, text=message, bg=THEME["bg_elevated"], fg=THEME["fg"],
                 font=("Microsoft YaHei", 11), wraplength=320, justify="left").pack(side="left", fill="both")

        self.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        px = (parent.winfo_width() - pw) // 2
        py = parent.winfo_height() - ph - 50
        self.geometry(f"+{parent.winfo_x()+px}+{parent.winfo_y()+py}")

        self.deiconify()
        self.lift()
        self.after(duration, self.destroy)


# ============================================================
# 圆角按钮
# ============================================================

class DarkButton(tk.Canvas):
    def __init__(self, parent, text, command=None, style="default", width=90, height=32, **kw):
        self._bg = kw.pop("bg", THEME["bg_elevated"])
        super().__init__(parent, width=width, height=height,
                         bg=self._bg, highlightthickness=0, bd=0, **kw)
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
                return THEME["accent_active"], "#ffffff", THEME["accent_active"], None
            if self._style == "danger":
                return THEME["error_hover"], "#ffffff", THEME["error_hover"], None
            if self._style == "success":
                return THEME["success"], "#ffffff", THEME["success"], None
            return THEME["bg_pressed"], THEME["fg"], THEME["border"], None
        if self._hover:
            if self._style == "accent":
                return THEME["accent_hover"], "#ffffff", THEME["accent_hover"], None
            if self._style == "danger":
                return THEME["error_hover"], "#ffffff", THEME["error_hover"], None
            if self._style == "success":
                return THEME["success_hover"], "#ffffff", THEME["success_hover"], None
            return THEME["bg_hover"], THEME["fg"], THEME["border"], None
        if self._style == "accent":
            return THEME["accent"], "#ffffff", THEME["accent"], None
        if self._style == "danger":
            return THEME["error"], "#ffffff", THEME["error"], None
        if self._style == "success":
            return THEME["success"], "#ffffff", THEME["success"], None
        return THEME["bg_elevated"], THEME["fg"], THEME["border"], None

    def _render(self):
        try:
            self.delete("all")
        except tk.TclError:
            return
        bg, fg, border, _ = self._colors()
        r = 8
        x1, y1, x2, y2 = 0, 0, self._cw, self._ch

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
        if not self._enabled: return
        self._hover = True
        self._render()

    def _on_leave(self, _):
        self._hover = False
        self._pressed = False
        try:
            self.configure(bg=self._bg)
            self._render()
        except tk.TclError:
            pass

    def _on_press(self, _):
        if not self._enabled: return
        self._pressed = True
        self._render()

    def _on_release(self, _):
        if not self._enabled: return
        self._pressed = False
        self._render()
        if self._command:
            self._command()

    def configure_state(self, enabled):
        self._enabled = enabled
        try:
            self.configure(bg=self._bg, cursor="hand2" if enabled else "arrow")
            self._render()
        except tk.TclError:
            pass


# ============================================================
# 输入框 / 文本域 / 进度条
# ============================================================

class DarkEntry(tk.Entry):
    def __init__(self, parent, textvariable=None, width=10, **kw):
        super().__init__(parent, textvariable=textvariable, width=width,
                         bg=THEME["bg_input"], fg=THEME["fg"],
                         insertbackground=THEME["accent"],
                         relief="solid", bd=1,
                         font=("Consolas", 10), **kw)


class DarkText(scrolledtext.ScrolledText):
    def __init__(self, parent, **kw):
        super().__init__(parent,
                         bg=THEME["log_bg"], fg=THEME["log_fg"],
                         insertbackground=THEME["accent"],
                         relief="solid", bd=1,
                         font=("Consolas", 10), wrap="word",
                         **kw)


class ProgressBar(tk.Canvas):
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
                                 fill="#e2e8f0", outline="")
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
# 主题
# ============================================================

def apply_light_theme(style):
    style.theme_use("clam")

    style.configure("Treeview",
                    background=THEME["bg_input"],
                    fieldbackground=THEME["bg_input"],
                    foreground=THEME["fg"],
                    borderwidth=0,
                    rowheight=36)
    style.configure("Treeview.Heading",
                    background=THEME["bg"],
                    foreground=THEME["fg_muted"],
                    relief="flat",
                    font=("Microsoft YaHei", 10, "bold"),
                    padding=10)
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
                    relief="solid",
                    padding=6)
    style.map("TCombobox",
              fieldbackground=[("readonly", THEME["bg_input"])],
              foreground=[("readonly", THEME["fg"])],
              arrowcolor=[("active", THEME["accent"])])

    style.configure("TFrame", background=THEME["bg"])
    style.configure("Card.TFrame", background=THEME["bg_elevated"])
    style.configure("Sidebar.TFrame", background=THEME["sidebar_bg"])
    style.configure("TLabel", background=THEME["bg"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 10))
    style.configure("Muted.TLabel", background=THEME["bg"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Card.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 10))
    style.configure("CardMuted.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Sidebar.TLabel", background=THEME["sidebar_bg"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 10))
    style.configure("SidebarMuted.TLabel", background=THEME["sidebar_bg"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Title.TLabel", background=THEME["bg"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 16, "bold"))
    style.configure("CardTitle.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 12, "bold"))
    style.configure("Hint.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_subtle"],
                    font=("Microsoft YaHei", 8))

    style.configure("TSeparator", background=THEME["border"])

    style.configure("Vertical.TScrollbar",
                    background=THEME["bg_elevated"],
                    troughcolor=THEME["bg"],
                    bordercolor=THEME["border"],
                    arrowcolor=THEME["fg_muted"],
                    gripcount=0, width=8)
    style.map("Vertical.TScrollbar",
              background=[("active", THEME["bg_hover"]), ("pressed", THEME["bg_pressed"])],
              arrowcolor=[("active", THEME["accent"])])

    style.configure("Horizontal.TScrollbar",
                    background=THEME["bg_elevated"],
                    troughcolor=THEME["bg"],
                    bordercolor=THEME["border"],
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
        bg = kw.pop("bg", THEME["sidebar_bg"])
        super().__init__(parent, bg=bg, **kw)
        self._canvas = tk.Canvas(self, width=14, height=14, bg=bg,
                                 highlightthickness=0, bd=0)
        self._canvas.pack(side="left", padx=(0, 10))
        self._dot = self._canvas.create_oval(3, 3, 11, 11, fill=THEME["fg_subtle"], outline="")
        self._pulse = None
        self._label = tk.Label(self, text="未连接", bg=bg,
                               fg=THEME["fg_muted"], font=("Microsoft YaHei", 10))
        self._label.pack(side="left")

    def _start_pulse(self):
        self._stop_pulse()
        def pulse():
            try:
                a = (time.time() * 3) % 1
                r = int(0xcb + a * (0x0e - 0xcb))
                g = int(0xd5 + a * (0xa5 - 0xd5))
                b = int(0xe1 + a * (0xe9 - 0xe1))
                self._canvas.itemconfig(self._dot, fill=f"#{r:02x}{g:02x}{b:02x}")
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
        self.root.minsize(1200, 750)
        self.root.resizable(False, False)
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
        apply_light_theme(self.style)

    # ======================== UI 构建 ========================

    def _build_ui(self):
        wrapper = tk.Frame(self.root, bg=THEME["bg"])
        wrapper.pack(fill="both", expand=True)

        # ---- 左侧边栏 ----
        sidebar = tk.Frame(wrapper, bg=THEME["sidebar_bg"], width=SIDEBAR_W)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        # 分隔线
        tk.Frame(wrapper, bg=THEME["sidebar_border"], width=1).pack(side="left", fill="y")

        # ---- 右侧主内容 ----
        content = tk.Frame(wrapper, bg=THEME["bg"])
        content.pack(side="left", fill="both", expand=True)

        # 顶部栏
        self._build_topbar(content)

        # 中间：收件人 + 配置
        mid = tk.Frame(content, bg=THEME["bg"])
        mid.pack(fill="both", expand=True, padx=20, pady=(12, 8))

        left_panel = tk.Frame(mid, bg=THEME["bg"])
        left_panel.pack(side="left", fill="both", expand=True)
        self._build_recipients_card(left_panel)

        right_panel = tk.Frame(mid, bg=THEME["bg"], width=340)
        right_panel.pack(side="right", fill="y", padx=(16, 0))
        right_panel.pack_propagate(False)
        self._build_config_card(right_panel)

        # 底部：日志 + 进度
        bottom = tk.Frame(content, bg=THEME["bg"])
        bottom.pack(fill="both", expand=True, padx=20, pady=(8, 20))
        self._build_bottom_card(bottom)

    # ---- 侧边栏 ----

    def _build_sidebar(self, parent):
        # Logo
        logo = tk.Frame(parent, bg=THEME["sidebar_bg"], padx=20, pady=24)
        logo.pack(fill="x")

        tk.Label(logo, text="💬", bg=THEME["sidebar_bg"],
                 font=("Segoe UI Emoji", 28)).pack(anchor="w")
        tk.Label(logo, text=APP_TITLE, bg=THEME["sidebar_bg"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 20, "bold")).pack(anchor="w", pady=(8, 0))
        tk.Label(logo, text="微信自动群发", bg=THEME["sidebar_bg"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(2, 0))

        tk.Frame(parent, bg=THEME["sidebar_border"], height=1).pack(fill="x", padx=20, pady=(0, 16))

        # 状态
        self.indicator = StatusIndicator(parent, bg=THEME["sidebar_bg"])
        self.indicator.pack(padx=20, anchor="w", pady=(0, 16))

        tk.Frame(parent, bg=THEME["sidebar_border"], height=1).pack(fill="x", padx=20, pady=(0, 16))

        # 收件人操作
        btn_z = tk.Frame(parent, bg=THEME["sidebar_bg"], padx=16)
        btn_z.pack(fill="x")

        tk.Label(btn_z, text="收件人", bg=THEME["sidebar_bg"], fg=THEME["fg_subtle"],
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", pady=(0, 6))

        self._sidebar_btn(btn_z, "➕ 添加收件人", self.add_recipient, "accent").pack(fill="x", pady=3)
        self._sidebar_btn(btn_z, "📋 批量添加", self.batch_add).pack(fill="x", pady=3)
        self._sidebar_btn(btn_z, "✏️ 编辑选中", self.edit_recipient).pack(fill="x", pady=3)
        self._sidebar_btn(btn_z, "🗑 删除选中", self.delete_recipient, "danger").pack(fill="x", pady=3)

        tk.Frame(parent, bg=THEME["sidebar_border"], height=1).pack(fill="x", padx=20, pady=12)

        # 工具箱
        btn_z2 = tk.Frame(parent, bg=THEME["sidebar_bg"], padx=16)
        btn_z2.pack(fill="x")

        tk.Label(btn_z2, text="工具箱", bg=THEME["sidebar_bg"], fg=THEME["fg_subtle"],
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", pady=(0, 6))

        self._sidebar_btn(btn_z2, "📚 消息模板", self._open_template_picker).pack(fill="x", pady=3)
        self._sidebar_btn(btn_z2, "🧪 测试发送", self.test_one).pack(fill="x", pady=3)

        tk.Frame(parent, bg=THEME["sidebar_border"], height=1).pack(fill="x", padx=20, pady=12)

        # 发送
        btn_z3 = tk.Frame(parent, bg=THEME["sidebar_bg"], padx=16)
        btn_z3.pack(fill="x")

        tk.Label(btn_z3, text="群发", bg=THEME["sidebar_bg"], fg=THEME["fg_subtle"],
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", pady=(0, 6))

        self.btn_send = DarkButton(btn_z3, "▶ 开始群发", command=self.start_send,
                                   style="accent", width=160, height=38, bg=THEME["sidebar_bg"])
        self.btn_send.pack(fill="x", pady=3)
        self.btn_stop = DarkButton(btn_z3, "⏹ 停止", command=self.stop_send,
                                   style="danger", width=160, height=32, bg=THEME["sidebar_bg"])
        self.btn_stop.pack(fill="x", pady=3)
        self.btn_stop.configure_state(False)

        # 底部占位 + 版本号
        tk.Frame(parent, bg=THEME["sidebar_bg"]).pack(fill="both", expand=True)
        tk.Label(parent, text="v1.0  ·  Nexori Studio", bg=THEME["sidebar_bg"],
                 fg=THEME["fg_subtle"], font=("Microsoft YaHei", 8)).pack(pady=(0, 16))

    def _sidebar_btn(self, parent, text, command, style="default"):
        return DarkButton(parent, text, command=command, style=style,
                          width=160, height=32, bg=THEME["sidebar_bg"])

    # ---- 顶部栏 ----

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=THEME["bg_elevated"], height=56)
        bar.pack(fill="x", padx=20, pady=(14, 0))
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=THEME["bg_elevated"], padx=20)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="收件人管理", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 13, "bold")).pack(side="left")

        self.var_count = tk.StringVar(value="共 0 条记录")
        count_lbl = tk.Label(inner, textvariable=self.var_count, bg=THEME["bg_elevated"],
                             fg=THEME["fg_muted"], font=("Microsoft YaHei", 10))
        count_lbl.pack(side="right", padx=(0, 8))

        self.var_status_top = tk.StringVar(value="")
        st_lbl = tk.Label(inner, textvariable=self.var_status_top, bg=THEME["bg_elevated"],
                          fg=THEME["accent"], font=("Microsoft YaHei", 9, "bold"))
        st_lbl.pack(side="right")

    # ---- 收件人卡片 ----

    def _build_recipients_card(self, parent):
        card = tk.Frame(parent, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True)

        pad = tk.Frame(card, bg=THEME["bg_elevated"], padx=16, pady=16)
        pad.pack(fill="both", expand=True)

        columns = ("name", "type", "message", "file", "schedule")
        self.tree = ttk.Treeview(pad, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="收件人名称", anchor="w")
        self.tree.heading("type", text="类型", anchor="center")
        self.tree.heading("message", text="消息内容", anchor="w")
        self.tree.heading("file", text="附件", anchor="center")
        self.tree.heading("schedule", text="定时", anchor="center")
        self.tree.column("name", width=170, anchor="w", stretch=False)
        self.tree.column("type", width=70, anchor="center", stretch=False)
        self.tree.column("message", width=260, anchor="w")
        self.tree.column("file", width=70, anchor="center", stretch=False)
        self.tree.column("schedule", width=100, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(pad, orient="vertical", command=self.tree.yview,
                            style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("oddrow", background=THEME["bg_elevated"])
        self.tree.tag_configure("evenrow", background=THEME["bg"])

    # ---- 配置卡片 ----

    def _build_config_card(self, parent):
        card = tk.Frame(parent, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True)

        pad = tk.Frame(card, bg=THEME["bg_elevated"], padx=16, pady=16)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="发送配置", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", pady=(0, 14))

        # 间隔设置
        tk.Label(pad, text="发送间隔（秒）", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(0, 4))

        delay_box = tk.Frame(pad, bg=THEME["bg_elevated"])
        delay_box.pack(fill="x", pady=(0, 6))

        self.var_min_delay = tk.StringVar(value=str(self.config["min_delay"]))
        self.var_max_delay = tk.StringVar(value=str(self.config["max_delay"]))

        DarkEntry(delay_box, textvariable=self.var_min_delay, width=6).pack(side="left")
        tk.Label(delay_box, text=" ~ ", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"]).pack(side="left")
        DarkEntry(delay_box, textvariable=self.var_max_delay, width=6).pack(side="left")
        tk.Label(delay_box, text="  随机", bg=THEME["bg_elevated"],
                 fg=THEME["fg_subtle"], font=("Microsoft YaHei", 9)).pack(side="left")

        self.var_retry = tk.IntVar(value=self.config["max_retries"])

        row2 = tk.Frame(pad, bg=THEME["bg_elevated"])
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="重试次数", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(side="left")
        ttk.Combobox(row2, textvariable=self.var_retry, state="readonly", width=4,
                     values=[0, 1, 2, 3]).pack(side="right")

        row3 = tk.Frame(pad, bg=THEME["bg_elevated"])
        row3.pack(fill="x", pady=(8, 0))
        tk.Label(row3, text="打开窗口等待（秒）", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(side="left")
        self.var_open_wait = tk.StringVar(value=str(self.config["open_window_wait"]))
        DarkEntry(row3, textvariable=self.var_open_wait, width=5).pack(side="right")

        row4 = tk.Frame(pad, bg=THEME["bg_elevated"])
        row4.pack(fill="x", pady=(8, 0))
        tk.Label(row4, text="发送后等待（秒）", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(side="left")
        self.var_send_wait = tk.StringVar(value=str(self.config["send_wait"]))
        DarkEntry(row4, textvariable=self.var_send_wait, width=5).pack(side="right")

        # 进度条
        tk.Label(pad, text="发送进度", bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(18, 4))
        self.progress = ProgressBar(pad, width=300, height=8, bg=THEME["bg_elevated"])
        self.progress.pack(fill="x")
        self.var_progress_text = tk.StringVar(value="")
        tk.Label(pad, textvariable=self.var_progress_text, bg=THEME["bg_elevated"],
                 fg=THEME["fg_subtle"], font=("Microsoft YaHei", 8)).pack(anchor="e", pady=(2, 0))

        # 倒计时
        self.var_countdown = tk.StringVar(value="")
        tk.Label(pad, textvariable=self.var_countdown, bg=THEME["bg_elevated"],
                 fg=THEME["warn"], font=("Microsoft YaHei", 10)).pack(anchor="e", pady=(8, 0))

    # ---- 底部卡片：日志 + 操作 ----

    def _build_bottom_card(self, parent):
        card = tk.Frame(parent, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                        highlightthickness=1)
        card.pack(fill="both", expand=True)

        pad = tk.Frame(card, bg=THEME["bg_elevated"], padx=16, pady=16)
        pad.pack(fill="both", expand=True)

        # 标题行
        header = tk.Frame(pad, bg=THEME["bg_elevated"])
        header.pack(fill="x", pady=(0, 8))

        tk.Label(header, text="运行日志", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 12, "bold")).pack(side="left")

        btn_row = tk.Frame(header, bg=THEME["bg_elevated"])
        btn_row.pack(side="right")
        DarkButton(btn_row, "🗑 清空日志", command=self._clear_log,
                   width=90, height=28, bg=THEME["bg_elevated"]).pack(side="left", padx=4)

        self.var_status_text = tk.StringVar(value="就绪")
        tk.Label(header, textvariable=self.var_status_text, bg=THEME["bg_elevated"],
                 fg=THEME["accent"], font=("Microsoft YaHei", 9, "bold")).pack(side="left", padx=16)

        # 日志框
        self.log_box = DarkText(pad, height=6)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    # ======================== 数据 ========================

    def _load_data(self):
        self.recipients = load_recipients(RECIPIENTS_FILE)
        self._refresh_tree()

    def _save_data(self):
        save_recipients(RECIPIENTS_FILE, self.recipients)

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        type_map = {"contact": "联系人", "group": "群聊"}
        for i, r in enumerate(self.recipients):
            tag = "oddrow" if i % 2 == 0 else "evenrow"
            attachments = split_files(r.get("file", ""))
            if attachments:
                file_disp = f"📎{len(attachments)}个" if len(attachments) > 1 else "📎1个"
            else:
                file_disp = "—"
            schedule = r.get("schedule", "")
            schedule_disp = f"⏰ {schedule}" if schedule else "—"
            self.tree.insert("", "end", values=(
                r["name"],
                type_map.get(r["type"], r["type"]),
                r.get("message", ""),
                file_disp,
                schedule_disp,
            ), tags=(tag,))
        self.var_count.set(f"共 {len(self.recipients)} 条记录")
        self._save_data()

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return -1
        return self.tree.index(sel[0])

    # ======================== 收件人操作 ========================

    def add_recipient(self):
        self._open_editor(None)

    def edit_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            Toast(self.root, "请先选择一位收件人", "warn")
            return
        self._open_editor(idx)

    def delete_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            Toast(self.root, "请先选择一位收件人", "warn")
            return
        name = self.recipients[idx]["name"]
        if messagebox.askyesno("确认删除", f"确定删除收件人 [{name}]？"):
            self.recipients.pop(idx)
            self._refresh_tree()
            Toast(self.root, f"已删除：{name}", "success")

    def batch_add(self):
        self._open_batch_editor()

    # ======================== 编辑弹窗 ========================

    def _open_editor(self, idx):
        is_edit = idx is not None
        win = tk.Toplevel(self.root)
        win.title("编辑收件人" if is_edit else "添加收件人")
        win.geometry("620x720")
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
        ttk.Combobox(outer, textvariable=var_type, state="readonly", width=12,
                     values=["contact", "group"]).grid(row=1, column=1, sticky="w", pady=6, padx=(12, 0))

        ttk.Label(outer, text="消息模板").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        msg_box = ttk.Frame(outer)
        msg_box.grid(row=2, column=1, sticky="we", pady=6, padx=(12, 0))
        msg_text = DarkText(msg_box, width=42, height=5)
        msg_text.pack(fill="both", expand=True)
        if is_edit:
            msg_text.insert("1.0", self.recipients[idx].get("message", ""))

        tpl_row = ttk.Frame(outer)
        tpl_row.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(0, 0))
        DarkButton(tpl_row, "📚 套用模板库", command=lambda: self._open_template_picker(
            on_pick=lambda tpl: (msg_text.delete("1.0", "end"), msg_text.insert("1.0", tpl))
        ), width=130, height=26, bg=THEME["bg"]).pack(side="left")
        ttk.Label(tpl_row, text="💡 可用 {name} 占位符", style="Muted.TLabel").pack(side="left", padx=8)

        ttk.Label(outer, text="定时").grid(row=4, column=0, sticky="w", pady=(8, 0))
        sched_box = ttk.Frame(outer)
        sched_box.grid(row=4, column=1, sticky="we", pady=(8, 0), padx=(12, 0))
        var_schedule = tk.StringVar(value=self.recipients[idx].get("schedule", "") if is_edit else "")
        DarkEntry(sched_box, textvariable=var_schedule, width=24).pack(side="left")
        ttk.Label(sched_box, text="如：14:30 或 2026-07-15 14:30", style="Hint.TLabel").pack(side="left", padx=8)

        ttk.Label(outer, text="附件").grid(row=5, column=0, sticky="nw", pady=(8, 0))
        file_box = tk.Frame(outer, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                            highlightthickness=1, padx=10, pady=10)
        file_box.grid(row=5, column=1, sticky="we", pady=(8, 0), padx=(12, 0))

        files_var = tk.StringVar(value=self.recipients[idx].get("file", "") if is_edit else "")
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

        tk.Label(file_box, textvariable=files_count_var, bg=THEME["bg_elevated"],
                 fg=THEME["accent"], font=("Microsoft YaHei", 9, "bold")).pack(anchor="e")
        tk.Label(file_box, textvariable=files_display_var, bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Consolas", 9), justify="left",
                 anchor="w", wraplength=360, height=4).pack(fill="x", pady=(2, 6))

        fbtn_row = tk.Frame(file_box, bg=THEME["bg_elevated"])
        fbtn_row.pack(fill="x")

        def pick_files():
            paths = filedialog.askopenfilenames(
                title="选择文件（可多选）",
                filetypes=[("所有文件", "*.*"), ("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                           ("文档", "*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt")],
            )
            if not paths: return
            existing = split_files(files_var.get())
            files_var.set("|".join(existing + list(paths)))
            refresh_files_display()

        def clear_files():
            files_var.set("")
            refresh_files_display()

        DarkButton(fbtn_row, "📁 多选文件", command=pick_files, style="accent",
                   width=110, height=28, bg=THEME["bg_elevated"]).pack(side="left", padx=2)
        DarkButton(fbtn_row, "🗑 清空", command=clear_files,
                   width=80, height=28, bg=THEME["bg_elevated"]).pack(side="left", padx=2)

        ttk.Label(file_box, text="💡 多个附件将按顺序逐个发送（图片轮播）",
                  style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        refresh_files_display()

        # 预览
        ttk.Label(outer, text="预览").grid(row=6, column=0, sticky="nw", pady=(8, 0))
        preview_var = tk.StringVar(value="")
        preview_box = tk.Frame(outer, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                               highlightthickness=1, padx=10, pady=10)
        preview_box.grid(row=6, column=1, sticky="we", pady=(8, 0), padx=(12, 0))
        tk.Label(preview_box, textvariable=preview_var, bg=THEME["bg_elevated"],
                 fg=THEME["accent"], font=("Microsoft YaHei", 10), wraplength=380,
                 justify="left", anchor="w").pack(fill="x")

        def update_preview(*_):
            name = var_name.get().strip() or "{name}"
            msg = msg_text.get("1.0", "end-1c")
            preview_var.set(msg.replace("{name}", name)[:200])

        var_name.trace_add("write", update_preview)
        msg_text.bind("<KeyRelease>", lambda e: update_preview())
        update_preview()

        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=(20, 0))

        def on_save():
            name = var_name.get().strip()
            rtype = var_type.get().strip() or "contact"
            message = msg_text.get("1.0", "end-1c")
            files = files_var.get().strip()
            schedule = var_schedule.get().strip()
            if schedule and parse_schedule(schedule) is None:
                Toast(win, "定时格式错误，正确示例：14:30 或 2026-07-15 14:30", "error")
                return
            if not name:
                Toast(win, "名称不能为空", "error")
                return
            data = {"name": name, "type": rtype, "message": message,
                    "file": files, "schedule": schedule}
            if is_edit:
                self.recipients[idx] = data
            else:
                self.recipients.append(data)
            self._refresh_tree()
            Toast(self.root, "保存成功", "success")
            win.destroy()

        DarkButton(btn_frame, "保存", command=on_save, style="accent",
                   width=90, height=32, bg=THEME["bg"]).pack(side="right", padx=4)
        DarkButton(btn_frame, "取消", command=win.destroy,
                   width=90, height=32, bg=THEME["bg"]).pack(side="right", padx=4)

    # ======================== 批量添加 ========================

    def _open_batch_editor(self):
        win = tk.Toplevel(self.root)
        win.title("批量添加收件人")
        win.geometry("860x680")
        win.configure(bg=THEME["bg"])
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=14)
        outer.pack(fill="both", expand=True)

        # 消息模板
        msg_card = tk.Frame(outer, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                            highlightthickness=1, padx=12, pady=12)
        msg_card.pack(fill="x", pady=(0, 10))

        head = tk.Frame(msg_card, bg=THEME["bg_elevated"])
        head.pack(fill="x")
        tk.Label(head, text="统一消息模板", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 12, "bold")).pack(side="left")
        DarkButton(head, "📚 模板库", command=lambda: self._open_template_picker(
            on_pick=lambda tpl: (batch_msg_text.delete("1.0", "end"), batch_msg_text.insert("1.0", tpl))
        ), width=100, height=24, bg=THEME["bg_elevated"]).pack(side="right")

        batch_msg_text = DarkText(msg_card, height=4)
        batch_msg_text.pack(fill="x", pady=(6, 4))
        batch_msg_text.insert("1.0", "你好 {name}，这是一条群发消息。")
        ttk.Label(msg_card, text="💡 可用 {name} 占位符，发送时自动替换",
                  style="Hint.TLabel").pack(anchor="w")

        # 附件
        file_card = tk.Frame(outer, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                             highlightthickness=1, padx=12, pady=12)
        file_card.pack(fill="x", pady=(0, 10))

        tk.Label(file_card, text="统一附件（多图轮播）", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 12, "bold")).pack(anchor="w")

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
                title="选择文件（可多选）",
                filetypes=[("所有文件", "*.*"), ("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                           ("文档", "*.pdf *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.txt")],
            )
            if not paths: return
            existing = split_files(batch_files_var.get())
            batch_files_var.set("|".join(existing + list(paths)))
            refresh_batch_files()

        def clear_batch_files():
            batch_files_var.set("")
            refresh_batch_files()

        info_row = tk.Frame(file_card, bg=THEME["bg_elevated"])
        info_row.pack(fill="x", pady=(6, 0))
        tk.Label(info_row, textvariable=batch_files_count, bg=THEME["bg_elevated"],
                 fg=THEME["accent"], font=("Microsoft YaHei", 9, "bold")).pack(side="right")
        tk.Label(info_row, textvariable=batch_files_display, bg=THEME["bg_elevated"],
                 fg=THEME["fg_muted"], font=("Consolas", 9), anchor="w").pack(side="left", fill="x", expand=True)

        fbtn_row = tk.Frame(file_card, bg=THEME["bg_elevated"])
        fbtn_row.pack(fill="x", pady=(4, 0))
        DarkButton(fbtn_row, "📁 多选文件", command=pick_batch_files, style="accent",
                   width=110, height=28, bg=THEME["bg_elevated"]).pack(side="left", padx=2)
        DarkButton(fbtn_row, "🗑 清空", command=clear_batch_files,
                   width=80, height=28, bg=THEME["bg_elevated"]).pack(side="left", padx=2)

        # 收件人表格
        list_card = tk.Frame(outer, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                             highlightthickness=1, padx=12, pady=12)
        list_card.pack(fill="both", expand=True)

        list_head = tk.Frame(list_card, bg=THEME["bg_elevated"])
        list_head.pack(fill="x")
        tk.Label(list_head, text="收件人列表", bg=THEME["bg_elevated"],
                 fg=THEME["fg"], font=("Microsoft YaHei", 12, "bold")).pack(side="left")
        tk.Label(list_head, text="双击编辑 / 右键删除", bg=THEME["bg_elevated"],
                 fg=THEME["fg_subtle"], font=("Microsoft YaHei", 9)).pack(side="left", padx=10)

        columns = ("idx", "type", "name", "schedule")
        batch_tree = ttk.Treeview(list_card, columns=columns, show="headings", height=8)
        batch_tree.heading("idx", text="#", anchor="center")
        batch_tree.heading("type", text="类型", anchor="center")
        batch_tree.heading("name", text="名称", anchor="w")
        batch_tree.heading("schedule", text="定时", anchor="center")
        batch_tree.column("idx", width=40, anchor="center", stretch=False)
        batch_tree.column("type", width=70, anchor="center", stretch=False)
        batch_tree.column("name", width=380, anchor="w")
        batch_tree.column("schedule", width=140, anchor="center", stretch=False)

        for i in range(1, 4):
            batch_tree.insert("", "end", iid=str(i), values=(i, "contact", "", ""))

        vsb = ttk.Scrollbar(list_card, orient="vertical", command=batch_tree.yview,
                            style="Vertical.TScrollbar")
        batch_tree.configure(yscrollcommand=vsb.set)
        batch_tree.pack(side="left", fill="both", expand=True, pady=(6, 0))
        vsb.pack(side="right", fill="y", pady=(6, 0))

        def refresh_indices():
            for i, item in enumerate(batch_tree.get_children(), start=1):
                vals = list(batch_tree.item(item, "values"))
                vals[0] = i
                batch_tree.item(item, values=vals)

        def _edit_row(item_id):
            vals = list(batch_tree.item(item_id, "values"))
            edit = tk.Toplevel(win)
            edit.title("编辑收件人")
            edit.geometry("460x320")
            edit.configure(bg=THEME["bg"])
            edit.transient(win)
            edit.grab_set()

            ef = ttk.Frame(edit, padding=16)
            ef.pack(fill="both", expand=True)
            ef.columnconfigure(1, weight=1)

            ttk.Label(ef, text="名称").grid(row=0, column=0, sticky="w", pady=8)
            v_name = tk.StringVar(value=vals[2])
            DarkEntry(ef, textvariable=v_name, width=32).grid(row=0, column=1, sticky="we", padx=(12, 0), pady=8)

            ttk.Label(ef, text="类型").grid(row=1, column=0, sticky="w", pady=8)
            v_type = tk.StringVar(value=vals[1] if vals[1] in ("contact", "group") else "contact")
            ttk.Combobox(ef, textvariable=v_type, state="readonly", width=12,
                         values=["contact", "group"]).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=8)

            ttk.Label(ef, text="定时").grid(row=2, column=0, sticky="w", pady=8)
            v_sched = tk.StringVar(value=vals[3] if len(vals) > 3 else "")
            DarkEntry(ef, textvariable=v_sched, width=24).grid(row=2, column=1, sticky="we", padx=(12, 0), pady=8)
            ttk.Label(ef, text="格式：14:30 或 2026-07-15 14:30（留空=立即发送）",
                      style="Hint.TLabel").grid(row=3, column=1, sticky="w", padx=(12, 0))

            btn_row = ttk.Frame(ef)
            btn_row.grid(row=4, column=0, columnspan=2, pady=(20, 0), sticky="e")

            def save_row():
                nm = v_name.get().strip()
                if not nm:
                    Toast(edit, "名称不能为空", "error")
                    return
                tp = v_type.get() if v_type.get() in ("contact", "group") else "contact"
                sc = v_sched.get().strip()
                if sc and parse_schedule(sc) is None:
                    Toast(edit, "定时格式错误", "error")
                    return
                batch_tree.item(item_id, values=(vals[0], tp, nm, sc))
                edit.destroy()

            DarkButton(btn_row, "保存", command=save_row, style="accent",
                       width=90, height=30, bg=THEME["bg"]).pack(side="right", padx=4)
            DarkButton(btn_row, "取消", command=edit.destroy,
                       width=90, height=30, bg=THEME["bg"]).pack(side="right", padx=4)

        batch_tree.bind("<Double-1>", lambda e: (
            _edit_row(batch_tree.focus()) if batch_tree.focus() else None
        ))

        def on_right_click(event):
            item = batch_tree.identify_row(event.y)
            if item:
                batch_tree.selection_set(item)
                menu = tk.Menu(win, tearoff=0)
                menu.add_command(label="✏️ 编辑", command=lambda: _edit_row(item))
                menu.add_command(label="🗑 删除", command=lambda: (batch_tree.delete(item), refresh_indices()))
                menu.tk_popup(event.x_root, event.y_root)

        batch_tree.bind("<Button-3>", on_right_click)

        # 按钮
        tree_btn_row = ttk.Frame(outer)
        tree_btn_row.pack(fill="x", pady=(8, 0))

        def add_row():
            iid = batch_tree.insert("", "end", values=("", "contact", "", ""))
            refresh_indices()
            _edit_row(iid)

        def del_row():
            for item in batch_tree.selection():
                batch_tree.delete(item)
            refresh_indices()

        def batch_import():
            try:
                import pyperclip
                text = pyperclip.paste()
                if not text:
                    Toast(win, "剪贴板为空", "warn")
                    return
                for item in list(batch_tree.get_children()):
                    vals = batch_tree.item(item, "values")
                    if not vals[2].strip():
                        batch_tree.delete(item)
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines:
                    rtype = "group" if (line.endswith("群") or line.endswith("Group")) else "contact"
                    batch_tree.insert("", "end", values=("", rtype, line, ""))
                refresh_indices()
                Toast(win, f"从剪贴板导入 {len(lines)} 条", "success")
            except Exception as e:
                Toast(win, f"导入失败: {e}", "error")

        DarkButton(tree_btn_row, "➕ 加行", command=add_row,
                   width=80, height=28, bg=THEME["bg"]).pack(side="left", padx=2)
        DarkButton(tree_btn_row, "➖ 删行", command=del_row,
                   width=80, height=28, bg=THEME["bg"]).pack(side="left", padx=2)
        DarkButton(tree_btn_row, "📋 从剪贴板导入", command=batch_import,
                   style="accent", width=140, height=28, bg=THEME["bg"]).pack(side="left", padx=2)

        # 底部
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(14, 0))

        def on_batch_save():
            template = batch_msg_text.get("1.0", "end-1c")
            files = batch_files_var.get().strip()
            added = 0
            for item in batch_tree.get_children():
                vals = batch_tree.item(item, "values")
                rtype, name = vals[1], vals[2].strip()
                schedule = vals[3] if len(vals) > 3 else ""
                if not name: continue
                self.recipients.append({
                    "name": name, "type": rtype if rtype in ("contact", "group") else "contact",
                    "message": template, "file": files, "schedule": schedule,
                })
                added += 1
            self._refresh_tree()
            Toast(self.root, f"已添加 {added} 位收件人", "success" if added else "warn")
            win.destroy()

        DarkButton(bottom, "保存", command=on_batch_save, style="accent",
                   width=120, height=32, bg=THEME["bg"]).pack(side="right", padx=4)
        DarkButton(bottom, "取消", command=win.destroy,
                   width=90, height=32, bg=THEME["bg"]).pack(side="right", padx=4)

    # ======================== 日志 ========================

    def _log(self, msg, level="info"):
        colors = {
            "info":      THEME["log_fg"],
            "success":   THEME["log_success"],
            "error":     THEME["log_error"],
            "warn":      THEME["log_warn"],
            "highlight": THEME["log_highlight"],
        }
        color = colors.get(level, THEME["log_fg"])
        ts = datetime.now().strftime("%H:%M:%S")

        def _append():
            try:
                self.log_box.configure(state="normal")
                self.log_box.insert("end", f"[{ts}] ", "ts")
                self.log_box.tag_configure("ts", foreground=THEME["fg_subtle"])
                self.log_box.insert("end", f"{msg}\n", level)
                self.log_box.tag_configure(level, foreground=color)
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            except tk.TclError:
                pass

        self.root.after(0, _append)

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass

    def _clear_log(self):
        try:
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
        except tk.TclError:
            pass

    # ======================== 微信状态 ========================

    def _check_wechat_status(self):
        if self.sending:
            return
        hwnd, title = find_wechat_window()
        if hwnd:
            self.indicator.set_state("ready")
            self.var_status_top.set(f"微信：{title[:20]}")
        else:
            self.indicator.set_state("idle")
            self.var_status_top.set("微信：未找到")
        self.root.after(5000, self._check_wechat_status)

    # ======================== 配置收集 ========================

    def _collect_config(self):
        try:
            min_delay = float(self.var_min_delay.get())
            max_delay = float(self.var_max_delay.get())
            retry = int(self.var_retry.get())
            open_wait = float(self.var_open_wait.get())
            send_wait = float(self.var_send_wait.get())
        except ValueError:
            Toast(self.root, "配置参数必须是数字", "error")
            return None
        if min_delay < 1 or max_delay < 1 or open_wait < 0.1 or send_wait < 0.1:
            Toast(self.root, "参数不能小于合理范围", "error")
            return None
        self.config.update({
            "min_delay": min_delay, "max_delay": max(max_delay, min_delay),
            "max_retries": retry, "open_window_wait": open_wait, "send_wait": send_wait,
        })
        return self.config

    # ======================== 发送控制 ========================

    def start_send(self):
        if self.sending:
            return
        if not self.recipients:
            Toast(self.root, "收件人列表为空", "warn")
            return
        config = self._collect_config()
        if config is None:
            return
        hwnd, _ = find_wechat_window()
        if not hwnd:
            if not messagebox.askyesno("未找到微信", "未检测到微信窗口，是否继续？"):
                return
        self.sending = True
        self.stop_flag = False
        self.btn_send.configure_state(False)
        self.btn_stop.configure_state(True)
        self.indicator.set_state("running")
        self.var_status_text.set("发送中...")

        self._log("=" * 40, "highlight")
        self._log("开始群发", "highlight")

        if not activate_wechat(lambda m: self._log(m, "info")):
            self._log("警告：无法激活微信窗口，尝试继续...", "warn")

        # 倒计时
        for i in range(3, 0, -1):
            self.var_countdown.set(f"⏳ {i} 秒后开始发送...")
            self._log(f"{i} 秒后开始发送...", "warn")
            self.root.update()
            time.sleep(1)
        self.var_countdown.set("")

        t = threading.Thread(target=self._send_worker, args=(config,), daemon=True)
        t.start()

    def stop_send(self):
        self.stop_flag = True
        self._log("用户手动停止", "warn")
        self.var_countdown.set("")

    def _update_progress(self, current, total):
        if total > 0:
            self.progress.set(current / total)
            self.var_progress_text.set(f"{current}/{total}")
        else:
            self.progress.set(0)
            self.var_progress_text.set("")

    def _send_worker(self, config):
        total = len(self.recipients)
        success, failed = [], []

        for idx, r in enumerate(self.recipients, start=1):
            if self.stop_flag:
                self._log("已手动停止", "warn")
                break

            # 定时
            schedule_str = r.get("schedule", "")
            if schedule_str:
                target = parse_schedule(schedule_str)
                if target and target > datetime.now():
                    wait_sec = (target - datetime.now()).total_seconds()
                    self._log(f"⏰ 等待到 {target.strftime('%Y-%m-%d %H:%M:%S')} 发送 {r['name']}（还需 {int(wait_sec)} 秒）", "warn")
                    while datetime.now() < target:
                        if self.stop_flag:
                            self._log("定时等待中被手动停止", "warn")
                            break
                        time.sleep(min(1.0, (target - datetime.now()).total_seconds()))
                    if self.stop_flag:
                        break

            self._update_progress(idx - 1, total)

            tag = "群聊" if r["type"] == "group" else "联系人"
            attachments = split_files(r.get("file", ""))
            if attachments:
                tag += f" 📎x{len(attachments)}"
            self._log(f"({idx}/{total}) [{tag}] {r['name']} ...", "info")

            ok, info = send_with_retry(r, config, lambda m: self._log(m, "info"))
            if ok:
                self._log(f"  ✓ {info}", "success")
                success.append(r["name"])
            else:
                self._log(f"  ✗ {info}", "error")
                failed.append((r["name"], info))
                if "紧急停止" in info:
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
            self.progress.set(0)
            self.var_progress_text.set("")
            hwnd, _ = find_wechat_window()
            self.indicator.set_state("ready" if hwnd else "idle")
        self.root.after(0, _update)

    # ======================== 测试发送 ========================

    def test_one(self):
        if self.sending:
            Toast(self.root, "群发进行中，请先停止", "warn")
            return
        idx = self._selected_index()
        if idx < 0:
            Toast(self.root, "请先选择一位收件人", "warn")
            return
        config = self._collect_config()
        if config is None:
            return
        hwnd, _ = find_wechat_window()
        if not hwnd:
            Toast(self.root, "未找到微信窗口", "error")
            return
        r = self.recipients[idx]
        if not messagebox.askyesno("测试发送", f"确定向 [{r['type']}] {r['name']} 发送一次测试消息？"):
            return
        self.sending = True
        self.btn_send.configure_state(False)
        self.indicator.set_state("running")
        self._log(f"🧪 测试发送 → {r['name']}", "highlight")
        if not activate_wechat(lambda m: self._log(m, "info")):
            self._log("测试失败：无法激活微信窗口", "error")
            self._finish_send()
            return
        for i in range(3, 0, -1):
            self._log(f"{i} 秒后开始测试...", "warn")
            self.root.update()
            time.sleep(1)
        t = threading.Thread(target=self._test_worker, args=(r, config), daemon=True)
        t.start()

    def _test_worker(self, recipient, config):
        ok, info = send_with_retry(recipient, config, lambda m: self._log(m, "info"))
        if ok:
            self._log(f"🧪 测试成功: {info}", "success")
            Toast(self.root, f"测试发送成功：{recipient['name']}", "success")
        else:
            self._log(f"🧪 测试失败: {info}", "error")
            Toast(self.root, f"测试失败：{info}", "error")
        self._finish_send()

    # ======================== 消息模板库 ========================

    def _open_template_picker(self, on_pick=None):
        win = tk.Toplevel(self.root)
        win.title("消息模板库")
        win.geometry("580x520")
        win.configure(bg=THEME["bg"])
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="📚 消息模板库", style="Title.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(outer, text="选择分类查看模板，点击「使用此模板」插入到消息框",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                        highlightthickness=1, padx=8, pady=8)
        left.pack(side="left", fill="y")

        right = tk.Frame(body, bg=THEME["bg_elevated"], highlightbackground=THEME["border"],
                         highlightthickness=1, padx=10, pady=10)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        categories = list(MESSAGE_TEMPLATES.keys())

        def on_cat_select(_):
            sel = cat_list.curselection()
            if not sel: return
            cat = categories[sel[0]]
            tpl_list.delete(0, "end")
            for t in MESSAGE_TEMPLATES[cat]:
                tpl_list.insert("end", t if t else "(自定义)")

        cat_list = tk.Listbox(left, bg=THEME["bg_elevated"], fg=THEME["fg"],
                              selectbackground=THEME["accent"], selectforeground="#ffffff",
                              font=("Microsoft YaHei", 11), borderwidth=0, highlightthickness=0,
                              width=12, height=10)
        for c in categories:
            cat_list.insert("end", c)
        cat_list.pack(fill="both", expand=True)
        cat_list.bind("<<ListboxSelect>>", on_cat_select)
        cat_list.selection_set(0)
        on_cat_select(None)

        tpl_list = tk.Listbox(right, bg=THEME["bg_elevated"], fg=THEME["fg"],
                              selectbackground=THEME["accent"], selectforeground="#ffffff",
                              font=("Microsoft YaHei", 11), borderwidth=0, highlightthickness=0,
                              width=40, height=10)
        tpl_list.pack(fill="both", expand=True)

        preview_var = tk.StringVar(value="")
        preview_lbl = tk.Label(right, textvariable=preview_var, bg=THEME["bg_elevated"],
                               fg=THEME["accent"], font=("Microsoft YaHei", 10),
                               wraplength=400, justify="left", anchor="w", height=4)
        preview_lbl.pack(fill="x", pady=(10, 0))

        def on_tpl_select(_):
            sel = tpl_list.curselection()
            if not sel: return
            preview_var.set(tpl_list.get(sel[0]).replace("{name}", "示例用户"))

        tpl_list.bind("<<ListboxSelect>>", on_tpl_select)

        def use_template():
            sel = tpl_list.curselection()
            if not sel:
                Toast(win, "请先选择一个模板", "warn")
                return
            txt = tpl_list.get(sel[0])
            if on_pick:
                on_pick(txt)
                Toast(win, "已套用模板", "success")
            win.destroy()

        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x", pady=(14, 0))
        DarkButton(btn_row, "使用此模板", command=use_template, style="accent",
                   width=130, height=32, bg=THEME["bg"]).pack(side="right", padx=4)
        DarkButton(btn_row, "关闭", command=win.destroy,
                   width=90, height=32, bg=THEME["bg"]).pack(side="right", padx=4)


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = MassSenderApp(root)
    root.mainloop()