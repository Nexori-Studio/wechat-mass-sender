# -*- coding: utf-8 -*-
"""
微信自动群发核心逻辑
====================
封装微信窗口激活、剪贴板、发送控制等所有核心操作，
供 GUI（gui.py）和 CLI（wechat_mass_sender.py）复用。

使用：from wechat_core import activate_wechat, send_one, send_with_retry, ...
"""

import os
import time
import csv
import random
from datetime import datetime


# ==================== 配置区 ====================

WECHAT_WINDOW_KEYWORDS = ("微信", "WeChat")

DEFAULT_CONFIG = {
    "min_delay": 5.0,
    "max_delay": 12.0,
    "step_delay": 0.8,
    "search_wait": 1.5,
    "max_retries": 2,
    "click_x_ratio": 0.5,
    "click_y_ratio": 0.85,
}


# ==================== 数据层 ====================

def load_recipients(path):
    """从 CSV 加载收件人列表。返回 list[dict]，字段：name, type, message"""
    if not os.path.exists(path):
        return []
    recipients = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"name", "type", "message"}.issubset(reader.fieldnames):
            return []
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            rtype = (row.get("type") or "contact").strip().lower()
            if rtype not in ("contact", "group"):
                rtype = "contact"
            message = row.get("message") or ""
            recipients.append({"name": name, "type": rtype, "message": message})
    return recipients


def save_recipients(path, recipients):
    """保存收件人列表到 CSV"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "type", "message"])
        writer.writeheader()
        for r in recipients:
            writer.writerow(r)


def render_message(template, name):
    """把 {name} 占位符替换为收件人名称"""
    return template.replace("{name}", name)


# ==================== 微信窗口操作 ====================

def find_wechat_window():
    """查找微信窗口句柄，返回 (hwnd, title) 或 (None, None)"""
    import win32gui

    results = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        for kw in WECHAT_WINDOW_KEYWORDS:
            if kw in title:
                results.append((hwnd, title))
                return

    win32gui.EnumWindows(callback, None)
    if results:
        return results[0]
    return None, None


def activate_wechat(log_cb=None, max_attempts=3):
    """强制激活微信窗口到前台。返回 True 表示已在前台。
    使用 AttachThreadInput + Alt 键技巧绕过 Windows 前台锁。
    """
    import win32gui
    import win32con
    import ctypes

    def _log(msg):
        if log_cb:
            log_cb(msg)

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd, title = find_wechat_window()
    if not hwnd:
        _log("错误：未找到微信窗口，请确保微信已登录且窗口未最小化")
        return False

    current_tid = kernel32.GetCurrentThreadId()

    for attempt in range(1, max_attempts + 1):
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.4)

            fg_hwnd = win32gui.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
            attached = False
            if fg_tid and fg_tid != current_tid:
                attached = bool(user32.AttachThreadInput(current_tid, fg_tid, True))
            try:
                # Alt 键技巧绕过前台锁
                user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
                user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    user32.AttachThreadInput(current_tid, fg_tid, False)

            time.sleep(0.4)

            if win32gui.GetForegroundWindow() == hwnd:
                return True

            if attempt < max_attempts:
                _log(f"激活尝试 {attempt} 未成功，重试...")
                time.sleep(0.5)
        except Exception as e:
            _log(f"激活异常(尝试 {attempt}): {e}")
            time.sleep(0.5)

    _log("错误：多次尝试仍无法把微信激活到前台（可能被系统前台锁拦截）")
    return False


def ensure_wechat_foreground(log_cb=None):
    """轻量检查：若微信已在前台直接返回 True，否则重新激活"""
    import win32gui
    hwnd, _ = find_wechat_window()
    if not hwnd:
        return False
    if win32gui.GetForegroundWindow() == hwnd:
        return True
    return activate_wechat(log_cb)


# ==================== 剪贴板 ====================

def set_clipboard(text):
    """将文本写入剪贴板（支持中文）"""
    import pyperclip
    pyperclip.copy(text)
    time.sleep(0.2)


# ==================== 核心发送 ====================

def send_one(name, message, config, log_cb=None):
    """向单个收件人发送一条消息。返回 (ok, info)"""
    import pyautogui
    import win32gui

    step_delay = config.get("step_delay", 0.8)
    search_wait = config.get("search_wait", 1.5)
    click_x_ratio = config.get("click_x_ratio", 0.5)
    click_y_ratio = config.get("click_y_ratio", 0.85)

    def _log(msg):
        if log_cb:
            log_cb(msg)

    if not activate_wechat(log_cb):
        return False, "无法激活微信窗口"

    time.sleep(step_delay)

    try:
        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        pyautogui.hotkey("ctrl", "f")
        time.sleep(step_delay)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        pyautogui.press("delete")
        time.sleep(0.2)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        set_clipboard(name)
        pyautogui.hotkey("ctrl", "v")
        _log(f"已输入搜索关键词: {name}")
        time.sleep(search_wait)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        pyautogui.press("enter")
        time.sleep(step_delay + 0.5)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        hwnd, _ = find_wechat_window()
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w = right - left
            h = bottom - top
            click_x = left + int(w * click_x_ratio)
            click_y = top + int(h * click_y_ratio)
            pyautogui.click(click_x, click_y)
            time.sleep(step_delay)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        set_clipboard(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(step_delay)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台（消息可能未发送）"
        pyautogui.press("enter")
        time.sleep(step_delay)

        _log("发送命令已执行")
        return True, "发送成功"

    except pyautogui.FailSafeException:
        return False, "用户触发紧急停止（鼠标移至左上角）"
    except Exception as e:
        return False, f"发送异常: {e}"


def send_with_retry(recipient, config, log_cb=None):
    """带重试的发送"""
    name = recipient["name"]
    message = render_message(recipient["message"], name)
    max_retries = config.get("max_retries", 2)

    for attempt in range(1, max_retries + 2):
        ok, info = send_one(name, message, config, log_cb)
        if ok:
            return True, info
        if "紧急停止" in info:
            return False, info
        if attempt <= max_retries:
            wait = 2 * attempt
            if log_cb:
                log_cb(f"  第{attempt}次失败，{wait}秒后重试: {info}")
            time.sleep(wait)
        else:
            return False, info


def send_batch(recipients, config, log_cb=None, stop_check=None):
    """批量发送。返回 (success_list, failed_list)
    stop_check: 可选回调，返回 True 时中止发送
    """
    success, failed = [], []
    total = len(recipients)

    for idx, r in enumerate(recipients, start=1):
        if stop_check and stop_check():
            if log_cb:
                log_cb("已手动停止")
            break

        tag = "群聊" if r["type"] == "group" else "联系人"
        if log_cb:
            log_cb(f"({idx}/{total}) [{tag}] {r['name']} ...")

        ok, info = send_with_retry(r, config, log_cb)
        if ok:
            if log_cb:
                log_cb(f"  ✓ {info}")
            success.append(r["name"])
        else:
            if log_cb:
                log_cb(f"  ✗ {info}")
            failed.append((r["name"], info))
            if "紧急停止" in info:
                if log_cb:
                    log_cb("检测到紧急停止信号，终止群发。")
                break

        if idx < total and not (stop_check and stop_check()):
            delay = random.uniform(config.get("min_delay", 5.0), config.get("max_delay", 12.0))
            time.sleep(delay)

    return success, failed


def make_log_file(prefix="mass_send"):
    """生成带时间戳的日志文件名"""
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
