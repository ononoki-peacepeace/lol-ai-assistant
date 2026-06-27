import win32gui


def enum_windows():
    results = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd)
        if title:
            results.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    return results


for hwnd, title in enum_windows():
    if "League" in title or "Riot" in title or "英雄联盟" in title:
        rect = win32gui.GetWindowRect(hwnd)
        print(hwnd, title, rect)