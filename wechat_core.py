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
    """从 CSV 加载收件人列表。返回 list[dict]，字段：name, type, message, file"""
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
            file_path = (row.get("file") or "").strip()
            recipients.append({
                "name": name,
                "type": rtype,
                "message": message,
                "file": file_path,
            })
    return recipients


def save_recipients(path, recipients):
    """保存收件人列表到 CSV"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "type", "message", "file"])
        writer.writeheader()
        for r in recipients:
            writer.writerow({
                "name": r.get("name", ""),
                "type": r.get("type", "contact"),
                "message": r.get("message", ""),
                "file": r.get("file", ""),
            })


def render_message(template, name):
    """把 {name} 占位符替换为收件人名称"""
    return template.replace("{name}", name)


def has_attachment(recipient):
    """判断收件人是否带附件"""
    return bool((recipient.get("file") or "").strip())


def split_files(file_field):
    """把 file 字段按 | 拆成多条文件路径（支持批量附件）"""
    if not file_field:
        return []
    return [p.strip() for p in str(file_field).split("|") if p.strip()]


def check_files_exist(recipient):
    """校验所有附件路径是否真实存在。返回 (ok, missing_list)"""
    missing = []
    for p in split_files(recipient.get("file", "")):
        if not os.path.exists(p):
            missing.append(p)
    return (len(missing) == 0, missing)


# ==================== 微信窗口操作 ====================

def find_wechat_window():
    """查找微信窗口句柄，返回 (hwnd, title) 或 (None, None)
    通过 className 精确匹配微信窗口（Qt51514QWindowIcon）
    """
    import win32gui

    results = []
    WECHAT_CLASSNAME = "Qt51514QWindowIcon"

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        className = win32gui.GetClassName(hwnd)
        if className != WECHAT_CLASSNAME:
            return
        title = win32gui.GetWindowText(hwnd)
        if title:
            results.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    if results:
        return results[0]
    return None, None


def activate_wechat(log_cb=None, max_attempts=3):
    """强制激活微信窗口到前台。返回 True 表示已在前台。
    诊断脚本验证：简单的 ShowWindow + SetForegroundWindow 在本环境有效。
    """
    import win32gui
    import win32con

    def _log(msg):
        if log_cb:
            log_cb(msg)

    hwnd, title = find_wechat_window()
    if not hwnd:
        _log("错误：未找到微信窗口，请确保微信已登录且窗口未最小化")
        return False

    _log(f"找到微信窗口: hwnd={hwnd}, title={title}")

    if win32gui.GetForegroundWindow() == hwnd:
        _log("微信已在前台")
        return True

    for attempt in range(1, max_attempts + 1):
        _log(f"激活尝试 {attempt}/{max_attempts}...")

        try:
            if win32gui.IsIconic(hwnd):
                _log("窗口处于最小化，先还原")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)

            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.4)

            if win32gui.GetForegroundWindow() == hwnd:
                _log("✅ 激活成功")
                return True

            if attempt < max_attempts:
                _log(f"激活尝试 {attempt} 未成功，1秒后重试...")
                time.sleep(1.0)
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

def navigate_to_chat(name, config, log_cb=None):
    """导航到指定联系人/群聊的聊天窗口。返回 ok, info
    通用步骤：激活微信 → Ctrl+F 搜索 → 粘贴名称 → Enter
    """
    import pyautogui

    step_delay = config.get("step_delay", 0.8)
    search_wait = config.get("search_wait", 1.5)

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
        return True, "已定位聊天"

    except pyautogui.FailSafeException:
        return False, "用户触发紧急停止（鼠标移至左上角）"
    except Exception as e:
        return False, f"导航异常: {e}"


def focus_input_box(config, log_cb=None):
    """点击微信窗口的输入框区域，使其获得焦点"""
    import pyautogui
    import win32gui

    step_delay = config.get("step_delay", 0.8)
    click_x_ratio = config.get("click_x_ratio", 0.5)
    click_y_ratio = config.get("click_y_ratio", 0.85)

    if not ensure_wechat_foreground(log_cb):
        return False
    hwnd, _ = find_wechat_window()
    if not hwnd:
        return False
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w = right - left
    h = bottom - top
    click_x = left + int(w * click_x_ratio)
    click_y = top + int(h * click_y_ratio)
    pyautogui.click(click_x, click_y)
    time.sleep(step_delay)
    return True


def send_file(file_path, config, log_cb=None):
    """发送一个文件/图片给当前打开的聊天窗口。
    图片走剪贴板（Ctrl+V），其他文件走文件路径直接粘贴（微信会识别为文件）。
    """
    import pyautogui

    step_delay = config.get("step_delay", 0.8)
    paste_wait = config.get("paste_wait", 1.2)

    def _log(msg):
        if log_cb:
            log_cb(msg)

    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

    try:
        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        set_clipboard(file_path)
        # 等待剪贴板更新
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "v")
        _log(f"  已粘贴: {os.path.basename(file_path)}")
        time.sleep(paste_wait)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        pyautogui.press("enter")
        time.sleep(step_delay)
        return True, f"已发送附件 {os.path.basename(file_path)}"

    except pyautogui.FailSafeException:
        return False, "用户触发紧急停止（鼠标移至左上角）"
    except Exception as e:
        return False, f"发送文件异常: {e}"


def send_one(name, message, config, log_cb=None):
    """向单个收件人发送一条文本消息。返回 (ok, info)"""
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
    """带重试的发送（支持文本 + 多文件/图片附件）
    流程：导航到聊天 → 发送文本（可选） → 逐个发送附件
    """
    name = recipient["name"]
    message = render_message(recipient.get("message", ""), name)
    file_paths = split_files(recipient.get("file", ""))
    max_retries = config.get("max_retries", 2)

    def _log(msg):
        if log_cb:
            log_cb(msg)

    for attempt in range(1, max_retries + 2):
        last_err = None

        # 1) 导航到聊天
        ok, info = navigate_to_chat(name, config, log_cb)
        if not ok:
            last_err = info
            if "紧急停止" in info:
                return False, info
        else:
            # 2) 点击输入框
            if not focus_input_box(config, log_cb):
                last_err = "无法定位输入框"
            else:
                # 3) 发送文本（如果有）
                if message and message.strip():
                    # 文本走 send_one 的剪贴板流程
                    ok, info = send_one_text_only(message, config, log_cb)
                    if not ok:
                        last_err = info
                    else:
                        last_err = None

                # 4) 逐个发送附件
                if last_err is None and file_paths:
                    for fp in file_paths:
                        ok, info = send_file(fp, config, log_cb)
                        if not ok:
                            last_err = info
                            break
                        time.sleep(0.3)

        if last_err is None:
            return True, "发送成功"
        if "紧急停止" in last_err:
            return False, last_err
        if attempt <= max_retries:
            wait = 2 * attempt
            _log(f"  第{attempt}次失败，{wait}秒后重试: {last_err}")
            time.sleep(wait)
        else:
            return False, last_err


def send_one_text_only(message, config, log_cb=None):
    """在已打开的聊天窗口中发送纯文本（依赖 focus_input_box 已先调用）"""
    import pyautogui
    step_delay = config.get("step_delay", 0.8)

    def _log(msg):
        if log_cb:
            log_cb(msg)

    try:
        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        set_clipboard(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(step_delay)

        if not ensure_wechat_foreground(log_cb):
            return False, "焦点丢失：微信不在前台"
        pyautogui.press("enter")
        time.sleep(step_delay)
        return True, "文本已发送"
    except pyautogui.FailSafeException:
        return False, "用户触发紧急停止（鼠标移至左上角）"
    except Exception as e:
        return False, f"发送文本异常: {e}"


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
        attachments = split_files(r.get("file", ""))
        if attachments:
            tag += f" 📎x{len(attachments)}"
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
