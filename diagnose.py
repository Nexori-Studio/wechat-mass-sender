import win32gui
import win32con
import win32api
import time
import os

WECHAT_WINDOW_KEYWORDS = ["微信"]

def find_wechat_window():
    results = []
    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        for kw in WECHAT_WINDOW_KEYWORDS:
            if kw in title:
                className = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                isIconic = win32gui.IsIconic(hwnd)
                results.append((hwnd, title, className, rect, isIconic))
                return
    win32gui.EnumWindows(callback, None)
    return results

def diagnose():
    print("=" * 60)
    print("微信窗口诊断工具")
    print("=" * 60)
    
    windows = find_wechat_window()
    print(f"\n[1] 找到 {len(windows)} 个微信窗口:")
    for i, (hwnd, title, className, rect, isIconic) in enumerate(windows):
        print(f"  [{i+1}] hwnd={hwnd}, title={repr(title)}")
        print(f"       className={repr(className)}, isIconic={isIconic}")
        print(f"       rect={rect} (left={rect[0]}, top={rect[1]}, width={rect[2]-rect[0]}, height={rect[3]-rect[1]})")
    
    if not windows:
        print("\n❌ 未找到微信窗口，请确保微信已登录")
        return
    
    hwnd = windows[0][0]
    fg_hwnd = win32gui.GetForegroundWindow()
    print(f"\n[2] 当前前台窗口: hwnd={fg_hwnd}, 是微信={fg_hwnd == hwnd}")
    
    print("\n[3] 尝试激活微信窗口...")
    for i in range(3):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        new_fg = win32gui.GetForegroundWindow()
        print(f"  尝试 {i+1}: 前台窗口={new_fg}, 是微信={new_fg == hwnd}")
        if new_fg == hwnd:
            print("  ✅ 激活成功!")
            break
    
    print("\n[4] 尝试微信快捷键 Ctrl+Alt+W...")
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32api.keybd_event(ord('W'), 0, 0, 0)
    time.sleep(0.3)
    win32api.keybd_event(ord('W'), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.6)
    fg_after = win32gui.GetForegroundWindow()
    print(f"  快捷键后前台窗口={fg_after}, 是微信={fg_after == hwnd}")
    
    print("\n" + "=" * 60)
    print("请将以上输出复制发给开发者")
    print("=" * 60)

if __name__ == "__main__":
    diagnose()