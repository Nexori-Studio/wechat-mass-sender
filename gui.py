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
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime

from wechat_core import (
    DEFAULT_CONFIG,
    load_recipients,
    save_recipients,
    find_wechat_window,
    activate_wechat,
    send_batch,
    make_log_file,
)

# ============================================================
# 主题：深色专业风
# ============================================================

THEME = {
    # 背景层级
    "bg":           "#1a1d23",   # 主背景
    "bg_elevated":  "#22262e",   # 卡片背景
    "bg_input":     "#2a2f38",   # 输入框背景
    "bg_hover":     "#323844",   # 悬停背景

    # 文本
    "fg":           "#e6e6e6",   # 主文本
    "fg_muted":     "#8b95a7",   # 次要文本
    "fg_subtle":    "#5a6273",   # 弱化文本

    # 边框
    "border":       "#2f3540",
    "border_focus": "#3d8bf2",

    # 强调色
    "accent":       "#3d8bf2",   # 蓝色主调
    "accent_hover": "#5294f5",
    "accent_active":"#2b7ae0",
    "success":      "#3ecf8e",   # 绿色
    "warn":         "#f0b429",   # 黄色
    "error":        "#ef4444",   # 红色

    # 日志
    "log_bg":       "#0f1115",
    "log_fg":       "#d4d4d4",
}

APP_TITLE = "微信自动群发工具"
APP_SIZE = "1000x720"
RECIPIENTS_FILE = "recipients.csv"


# ============================================================
# 自定义控件
# ============================================================

class DarkButton(tk.Canvas):
    """自绘扁平化深色按钮（支持悬停/按下/禁用状态）"""

    def __init__(self, parent, text, command=None, style="default", width=90, height=32, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=THEME["bg"], highlightthickness=0, bd=0, **kw)
        self._text = text
        self._command = command
        self._enabled = True
        self._style = style
        self._cw, self._ch = width, height
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._render()

    def _colors(self):
        if not self._enabled:
            return THEME["bg_elevated"], THEME["fg_subtle"], THEME["border"]
        if self._style == "accent":
            return THEME["accent"], "#ffffff", THEME["accent"]
        if self._style == "danger":
            return THEME["error"], "#ffffff", THEME["error"]
        return THEME["bg_elevated"], THEME["fg"], THEME["border"]

    def _render(self):
        # 安全删除：先检查 widget 是否还有效
        try:
            self.delete("all")
        except tk.TclError:
            return
        bg, fg, border = self._colors()
        r = 6
        # 用 polygon 模拟圆角矩形
        x1, y1, x2, y2 = 1, 1, self._cw - 1, self._ch - 1
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
        self.create_polygon(points, smooth=True, fill=bg, outline=border, width=1)
        self.create_text(self._cw / 2, self._ch / 2, text=self._text,
                         fill=fg, font=("Microsoft YaHei", 10, "bold"))

    def _on_enter(self, _):
        if not self._enabled:
            return
        if self._style == "accent":
            self.configure(bg=THEME["accent_hover"])
        else:
            self.configure(bg=THEME["bg_hover"])
        self._render()

    def _on_leave(self, _):
        try:
            self.configure(bg=THEME["bg"])
            self._render()
        except tk.TclError:
            pass

    def _on_click(self, _):
        if self._enabled and self._command:
            self._command()

    def configure_state(self, enabled):
        self._enabled = enabled
        try:
            self.configure(bg=THEME["bg"], cursor="hand2" if enabled else "arrow")
            self._render()
        except tk.TclError:
            pass


class DarkEntry(tk.Entry):
    """深色输入框"""
    def __init__(self, parent, textvariable=None, width=10, **kw):
        super().__init__(parent, textvariable=textvariable, width=width,
                         bg=THEME["bg_input"], fg=THEME["fg"],
                         insertbackground=THEME["fg"],
                         relief="flat", bd=0, highlightthickness=1,
                         highlightcolor=THEME["border_focus"],
                         highlightbackground=THEME["border"],
                         font=("Consolas", 10), **kw)


class DarkText(scrolledtext.ScrolledText):
    """深色日志框"""
    def __init__(self, parent, **kw):
        super().__init__(parent,
                         bg=THEME["log_bg"], fg=THEME["log_fg"],
                         insertbackground="#ffffff",
                         relief="flat", bd=0, highlightthickness=0,
                         font=("Consolas", 10), wrap="word",
                         **kw)


# ============================================================
# 主题应用到 ttk 控件
# ============================================================

def apply_dark_theme(style):
    style.theme_use("clam")

    # Treeview
    style.configure("Treeview",
                    background=THEME["bg_elevated"],
                    fieldbackground=THEME["bg_elevated"],
                    foreground=THEME["fg"],
                    bordercolor=THEME["border"],
                    borderwidth=0,
                    rowheight=30)
    style.configure("Treeview.Heading",
                    background=THEME["bg_input"],
                    foreground=THEME["fg_muted"],
                    relief="flat",
                    font=("Microsoft YaHei", 10, "bold"))
    style.map("Treeview",
              background=[("selected", THEME["accent"])],
              foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading",
              background=[("active", THEME["bg_hover"])])

    # Combobox
    style.configure("TCombobox",
                    fieldbackground=THEME["bg_input"],
                    background=THEME["bg_input"],
                    foreground=THEME["fg"],
                    arrowcolor=THEME["fg_muted"],
                    bordercolor=THEME["border"],
                    lightcolor=THEME["border"],
                    darkcolor=THEME["border"],
                    relief="flat")
    style.map("TCombobox",
              fieldbackground=[("readonly", THEME["bg_input"])],
              foreground=[("readonly", THEME["fg"])],
              selectbackground=[("readonly", THEME["bg_input"])],
              selectforeground=[("readonly", THEME["fg"])])

    # TFrame / TLabel
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
                    font=("Microsoft YaHei", 14, "bold"))
    style.configure("CardTitle.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg"],
                    font=("Microsoft YaHei", 11, "bold"))
    style.configure("Status.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 9))
    style.configure("Hint.TLabel", background=THEME["bg_elevated"], foreground=THEME["fg_subtle"],
                    font=("Microsoft YaHei", 9))

    # LabelFrame
    style.configure("Card.TLabelframe",
                    background=THEME["bg_elevated"],
                    foreground=THEME["fg"],
                    bordercolor=THEME["border"],
                    relief="flat",
                    borderwidth=1)
    style.configure("Card.TLabelframe.Label",
                    background=THEME["bg_elevated"],
                    foreground=THEME["fg_muted"],
                    font=("Microsoft YaHei", 10, "bold"))

    # Separator
    style.configure("TSeparator", background=THEME["border"])

    # Scrollbar
    style.configure("Vertical.TScrollbar",
                    background=THEME["bg_elevated"],
                    troughcolor=THEME["bg"],
                    bordercolor=THEME["bg"],
                    arrowcolor=THEME["fg_muted"],
                    gripcount=0)
    style.map("Vertical.TScrollbar",
              background=[("active", THEME["bg_hover"])])


# ============================================================
# 状态指示器
# ============================================================

class StatusIndicator(tk.Frame):
    """左上角圆点状态指示"""
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=THEME["bg"], **kw)
        self._canvas = tk.Canvas(self, width=10, height=10,
                                 bg=THEME["bg"], highlightthickness=0, bd=0)
        self._canvas.pack(side="left", padx=(0, 6))
        self._dot = self._canvas.create_oval(2, 2, 8, 8, fill=THEME["fg_subtle"], outline="")
        self._label = tk.Label(self, text="未连接", bg=THEME["bg"],
                               fg=THEME["fg_muted"], font=("Microsoft YaHei", 9))
        self._label.pack(side="left")

    def set_state(self, state):
        """state: idle / ready / running / error"""
        states = {
            "idle":    (THEME["fg_subtle"], "未连接"),
            "ready":   (THEME["success"], "微信已就绪"),
            "running": (THEME["warn"], "发送中..."),
            "error":   (THEME["error"], "异常"),
        }
        color, text = states.get(state, states["idle"])
        self._canvas.itemconfig(self._dot, fill=color)
        self._label.configure(text=text)


# ============================================================
# 主应用
# ============================================================

class MassSenderApp:

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(APP_SIZE)
        self.root.minsize(900, 640)
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

        # 周期性检查微信状态
        self.root.after(2000, self._check_wechat_status)

    def _build_style(self):
        self.style = ttk.Style()
        apply_dark_theme(self.style)

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(16, 8))

        ttk.Label(header, text="微信自动群发", style="Title.TLabel").pack(side="left")

        # 状态指示器
        self.indicator = StatusIndicator(header)
        self.indicator.pack(side="right", padx=(0, 12))

        # 分隔
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20)

        # 主区域：左收件人 + 右配置日志
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

    def _build_recipients_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True)

        # 标题行
        title_bar = ttk.Frame(card, style="Card.TFrame")
        title_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(title_bar, text="收件人", style="CardTitle.TLabel").pack(side="left")

        # 操作按钮
        btn_box = ttk.Frame(title_bar, style="Card.TFrame")
        btn_box.pack(side="right")

        self.btn_add = DarkButton(btn_box, "➕ 添加", command=self.add_recipient, width=72, height=28)
        self.btn_add.pack(side="left", padx=2)
        self.btn_edit = DarkButton(btn_box, "✏️ 编辑", command=self.edit_recipient, width=72, height=28)
        self.btn_edit.pack(side="left", padx=2)
        self.btn_del = DarkButton(btn_box, "🗑 删除", command=self.delete_recipient, width=72, height=28)
        self.btn_del.pack(side="left", padx=2)

        # 表格
        table_frame = ttk.Frame(card, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "type", "message")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        self.tree.heading("name", text="名称", anchor="w")
        self.tree.heading("type", text="类型", anchor="center")
        self.tree.heading("message", text="消息模板", anchor="w")
        self.tree.column("name", width=160, anchor="w", stretch=False)
        self.tree.column("type", width=70, anchor="center", stretch=False)
        self.tree.column("message", width=320, anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview,
                            style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 斑马纹
        self.tree.tag_configure("oddrow", background=THEME["bg_elevated"])
        self.tree.tag_configure("evenrow", background="#262b34")

        self.tree.bind("<Double-1>", lambda e: self.edit_recipient())

        # 底部状态 + 导入保存
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

        # 第一行
        row1 = ttk.Frame(card, style="Card.TFrame")
        row1.pack(fill="x", pady=4)

        self._labeled_entry(row1, "最小延时(秒)", "var_min_delay", str(self.config["min_delay"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row1, "最大延时(秒)", "var_max_delay", str(self.config["max_delay"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row1, "重试次数", "var_max_retries", str(self.config["max_retries"]), width=4).pack(side="left", padx=(0, 16))

        # 第二行
        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=4)

        self._labeled_entry(row2, "点击 X 比例", "var_click_x", str(self.config["click_x_ratio"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row2, "点击 Y 比例", "var_click_y", str(self.config["click_y_ratio"])).pack(side="left", padx=(0, 16))
        self._labeled_entry(row2, "搜索等待(秒)", "var_search_wait", str(self.config["search_wait"])).pack(side="left", padx=(0, 16))

        # 操作栏
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
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_configure("info", foreground=THEME["log_fg"])
        self.log_text.tag_configure("success", foreground=THEME["success"])
        self.log_text.tag_configure("error", foreground=THEME["error"])
        self.log_text.tag_configure("warn", foreground=THEME["warn"])
        self.log_text.tag_configure("highlight", foreground=THEME["accent"])

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
            self.tree.insert("", "end", values=(r["name"], type_map.get(r["type"], r["type"]), r["message"]),
                             tags=(tag,))
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
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

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
                messagebox.showwarning("提示", "文件中没有有效的收件人数据")
                return
            if messagebox.askyesno("确认", f"读取到 {len(data)} 条记录，是否替换当前列表？"):
                self.recipients = data
                self._refresh_tree()
                self._log(f"已导入 {len(data)} 条记录", "success")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    # ---------------- 增删改 ----------------

    def add_recipient(self):
        self._open_editor(None)

    def edit_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            messagebox.showinfo("提示", "请先选择一条记录")
            return
        self._open_editor(idx)

    def delete_recipient(self):
        idx = self._selected_index()
        if idx < 0:
            messagebox.showinfo("提示", "请先选择一条记录")
            return
        name = self.recipients[idx]["name"]
        if messagebox.askyesno("确认删除", f"确定删除「{name}」吗？"):
            del self.recipients[idx]
            self._refresh_tree()

    def _open_editor(self, idx):
        is_edit = idx is not None
        win = tk.Toplevel(self.root)
        win.title("编辑收件人" if is_edit else "添加收件人")
        win.geometry("500x420")
        win.resizable(False, False)
        win.configure(bg=THEME["bg"])
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=16)
        outer.pack(fill="both", expand=True)

        # 名称
        ttk.Label(outer, text="名称").grid(row=0, column=0, sticky="w", pady=6)
        var_name = tk.StringVar(value=self.recipients[idx]["name"] if is_edit else "")
        DarkEntry(outer, textvariable=var_name, width=36).grid(row=0, column=1, sticky="w", pady=6, padx=(12, 0))

        # 类型
        ttk.Label(outer, text="类型").grid(row=1, column=0, sticky="w", pady=6)
        var_type = tk.StringVar(value=self.recipients[idx]["type"] if is_edit else "contact")
        type_combo = ttk.Combobox(outer, textvariable=var_type, state="readonly", width=12,
                                  values=["contact", "group"])
        type_combo.grid(row=1, column=1, sticky="w", pady=6, padx=(12, 0))

        # 消息
        ttk.Label(outer, text="消息模板").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        msg_box = ttk.Frame(outer)
        msg_box.grid(row=2, column=1, sticky="w", pady=6, padx=(12, 0))
        msg_text = DarkText(msg_box, width=42, height=9)
        msg_text.pack(fill="both", expand=True)
        if is_edit:
            msg_text.insert("1.0", self.recipients[idx]["message"])

        # 提示
        ttk.Label(outer, text="💡 可用 {name} 作为名称占位符",
                  style="Muted.TLabel").grid(row=3, column=1, sticky="w", pady=(4, 0))

        # 预览
        ttk.Label(outer, text="预览").grid(row=4, column=0, sticky="nw", pady=(8, 0))
        preview_var = tk.StringVar(value="")
        preview_box = ttk.Frame(outer, style="Card.TFrame", padding=10)
        preview_box.grid(row=4, column=1, sticky="we", pady=(8, 0), padx=(12, 0))
        preview_lbl = tk.Label(preview_box, textvariable=preview_var,
                               bg=THEME["bg_elevated"], fg=THEME["accent"],
                               font=("Microsoft YaHei", 10), wraplength=360,
                               justify="left", anchor="w")
        preview_lbl.pack(fill="x")

        def update_preview(*_):
            name = var_name.get().strip() or "{name}"
            msg = msg_text.get("1.0", "end-1c")
            preview_var.set(msg.replace("{name}", name)[:200])

        var_name.trace_add("write", update_preview)
        msg_text.bind("<KeyRelease>", lambda e: update_preview())
        update_preview()

        # 按钮
        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(20, 0))

        def on_save():
            name = var_name.get().strip()
            rtype = var_type.get().strip() or "contact"
            message = msg_text.get("1.0", "end-1c")
            if not name:
                messagebox.showwarning("提示", "名称不能为空")
                return
            if is_edit:
                self.recipients[idx] = {"name": name, "type": rtype, "message": message}
            else:
                self.recipients.append({"name": name, "type": rtype, "message": message})
            self._refresh_tree()
            win.destroy()

        DarkButton(btn_frame, "保存", command=on_save, style="accent", width=90, height=32).pack(side="right", padx=4)
        DarkButton(btn_frame, "取消", command=win.destroy, width=90, height=32).pack(side="right", padx=4)

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
            messagebox.showerror("配置错误", f"请检查配置项，输入的不是有效数字：{e}")
            return None

    def start_send(self):
        if self.sending:
            return
        if not self.recipients:
            messagebox.showinfo("提示", "收件人列表为空，请先添加收件人")
            return

        config = self._collect_config()
        if config is None:
            return

        hwnd, _ = find_wechat_window()
        if not hwnd:
            messagebox.showwarning("未检测到微信",
                                   "未找到微信窗口！\n\n请先登录电脑版微信，并保持窗口可见（不要最小化）。")
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

        self._log(f"开始群发，共 {count} 位收件人", "highlight")

        # 主线程预激活
        self._log("正在激活微信窗口...", "info")
        if not activate_wechat(lambda m: self._log(m, "info")):
            self._log("预检失败：无法激活微信窗口，已中止", "error")
            self._finish_send()
            messagebox.showerror("激活失败",
                                 "无法把微信窗口激活到前台。\n\n"
                                 "可能原因：\n"
                                 "1. 微信被其他全屏应用遮挡\n"
                                 "2. 系统前台锁限制\n"
                                 "3. 微信窗口最小化\n\n"
                                 "请手动点击一下微信窗口使其前置，再重试。")
            return

        # 倒计时
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

    def _send_worker(self, config):
        success, failed = send_batch(
            self.recipients, config,
            log_cb=lambda m: self._log(m, "info"),
            stop_check=lambda: self.stop_flag,
        )

        total = len(self.recipients)
        self._log("=" * 40, "highlight")
        self._log(f"完成：成功 {len(success)} / 失败 {len(failed)} / 共 {total}", "highlight")
        if failed:
            self._log("失败列表：", "warn")
            for name, info in failed:
                self._log(f"  - {name}: {info}", "error")

        # 写入文件日志
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"\n完成：成功 {len(success)} / 失败 {len(failed)} / 共 {total}\n")
                for name, info in failed:
                    f.write(f"  - {name}: {info}\n")
        except Exception:
            pass

        self.var_count.set(f"本次: 成功 {len(success)} / 失败 {len(failed)}")
        self._finish_send()

    def _finish_send(self):
        def _update():
            self.sending = False
            self.stop_flag = False
            self.btn_send.configure_state(True)
            self.btn_stop.configure_state(False)
            hwnd, _ = find_wechat_window()
            self.indicator.set_state("ready" if hwnd else "idle")

        self.root.after(0, _update)


# ============================================================
# 入口
# ============================================================

def main():
    root = tk.Tk()
    app = MassSenderApp(root)
    app._log("请确认微信已登录并保持窗口可见", "info")
    root.mainloop()


if __name__ == "__main__":
    main()
