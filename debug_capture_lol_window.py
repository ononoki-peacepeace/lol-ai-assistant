from pathlib import Path
import ctypes

import cv2
import mss
import numpy as np
import win32gui


# 解决 Windows DPI 缩放导致坐标偏移的问题
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "debug_output" / "lol_window_client.png"


def find_lol_window():
    candidates = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd)

        if "League of Legends" in title or "英雄联盟" in title:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            candidates.append((hwnd, title, width * height, (left, top, right, bottom)))

    win32gui.EnumWindows(callback, None)

    if not candidates:
        raise RuntimeError("没有找到 League of Legends 窗口")

    candidates.sort(key=lambda x: x[2], reverse=True)

    print("找到的候选窗口：")
    for hwnd, title, area, rect in candidates:
        print(hwnd, title, rect)

    return candidates[0][0]


def get_client_region(hwnd):
    # 获取窗口客户区大小，不包含标题栏、边框
    left, top, right, bottom = win32gui.GetClientRect(hwnd)

    # 客户区左上角转换到屏幕坐标
    screen_left, screen_top = win32gui.ClientToScreen(hwnd, (left, top))
    screen_right, screen_bottom = win32gui.ClientToScreen(hwnd, (right, bottom))

    return {
        "left": screen_left,
        "top": screen_top,
        "width": screen_right - screen_left,
        "height": screen_bottom - screen_top,
    }


def capture_region(region):
    with mss.mss() as sct:
        img = np.array(sct.grab(region))

    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    hwnd = find_lol_window()
    region = get_client_region(hwnd)

    print(f"使用窗口 hwnd={hwnd}")
    print(f"客户区截图区域: {region}")

    img = capture_region(region)
    cv2.imwrite(str(OUTPUT_PATH), img)

    print(f"已保存截图: {OUTPUT_PATH}")
    print(f"截图尺寸: {img.shape[1]} x {img.shape[0]}")


if __name__ == "__main__":
    main()