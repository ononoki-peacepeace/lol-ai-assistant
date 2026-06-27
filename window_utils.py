import ctypes
import win32gui


try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


def find_lol_window():
    """
    查找 League of Legends 客户端窗口。
    返回 hwnd。
    """
    candidates = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd)

        if "League of Legends" in title or "英雄联盟" in title:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            area = width * height

            candidates.append(
                {
                    "hwnd": hwnd,
                    "title": title,
                    "area": area,
                    "rect": (left, top, right, bottom),
                }
            )

    win32gui.EnumWindows(callback, None)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["area"], reverse=True)
    return candidates[0]["hwnd"]


def get_client_region(hwnd):
    """
    获取窗口客户区，不包含标题栏和边框。
    返回 mss 可用的 region。
    """
    left, top, right, bottom = win32gui.GetClientRect(hwnd)

    screen_left, screen_top = win32gui.ClientToScreen(hwnd, (left, top))
    screen_right, screen_bottom = win32gui.ClientToScreen(hwnd, (right, bottom))

    return {
        "left": screen_left,
        "top": screen_top,
        "width": screen_right - screen_left,
        "height": screen_bottom - screen_top,
    }


def get_lol_client_region():
    hwnd = find_lol_window()

    if hwnd is None:
        return None

    return get_client_region(hwnd)