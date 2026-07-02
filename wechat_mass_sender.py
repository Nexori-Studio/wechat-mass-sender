# -*- coding: utf-8 -*-
"""
微信 PC 版自动群发消息脚本（命令行版）
=======================================
用法：python wechat_mass_sender.py [可选：recipients.csv 路径]

与 GUI 版本共享核心逻辑（wechat_core.py），行为完全一致。
"""

import sys
import time
from datetime import datetime

from wechat_core import (
    DEFAULT_CONFIG,
    load_recipients,
    render_message,
    activate_wechat,
    send_batch,
    make_log_file,
)


RECIPIENTS_FILE = "recipients.csv"
CONFIRM_BEFORE_SEND = True


def log(msg, log_file=None):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def preview_plan(recipients):
    print("\n" + "=" * 60)
    print(f"群发计划：共 {len(recipients)} 条")
    print("-" * 60)
    for idx, r in enumerate(recipients, start=1):
        rendered = render_message(r["message"], r["name"])
        tag = "群聊" if r["type"] == "group" else "联系人"
        print(f"{idx:>2}. [{tag}] {r['name']}")
        print(f"     消息: {rendered}")
    print("=" * 60)


def confirm():
    if not CONFIRM_BEFORE_SEND:
        return True
    print("\n⚠️  即将开始群发！发送过程中请勿操作鼠标键盘。")
    print("   紧急停止：将鼠标快速移到屏幕左上角。")
    ans = input("确认发送？输入 y 继续，其他取消: ").strip().lower()
    return ans == "y"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else RECIPIENTS_FILE
    log_file = make_log_file()

    print("=" * 60)
    print("  微信 PC 版自动群发工具（命令行版）")
    print("=" * 60)

    recipients = load_recipients(csv_path)
    if not recipients:
        print(f"收件人名单为空或不存在：{csv_path}")
        return

    preview_plan(recipients)
    if not confirm():
        print("已取消。")
        return

    # 主线程预激活
    log("正在激活微信窗口...", log_file)
    if not activate_wechat(lambda m: log(m, log_file)):
        log("预检失败：无法激活微信窗口，已中止", log_file)
        return

    # 倒计时
    for i in range(3, 0, -1):
        log(f"{i} 秒后开始发送...", log_file)
        time.sleep(1)

    log(f"开始群发，共 {len(recipients)} 位收件人", log_file)

    success, failed = send_batch(
        recipients, DEFAULT_CONFIG,
        log_cb=lambda m: log(m, log_file),
    )

    total = len(recipients)
    log("=" * 40, log_file)
    log(f"完成：成功 {len(success)} / 失败 {len(failed)} / 共 {total}", log_file)
    if failed:
        log("失败列表：", log_file)
        for name, info in failed:
            log(f"  - {name}: {info}", log_file)
    print(f"\n日志已保存至: {log_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，已停止发送。")
