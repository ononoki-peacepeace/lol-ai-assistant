import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

from screen_capture import ScreenCapture
from config import BASE_DIR


DATA_DIR = BASE_DIR / "data"
LAYOUT_FILE = DATA_DIR / "layout.json"
DEBUG_DIR = BASE_DIR / "debug_output"

POINT_LABELS = [
    "blue_ban_first",
    "blue_ban_last",
    "red_ban_first",
    "red_ban_last",
    "blue_pick_first",
    "blue_pick_last",
    "red_pick_first",
    "red_pick_last",
]

POINT_DESCRIPTIONS = {
    "blue_ban_first": "Blue Ban 1 center",
    "blue_ban_last": "Blue Ban 5 center",
    "red_ban_first": "Red Ban 1 center",
    "red_ban_last": "Red Ban 5 center",
    "blue_pick_first": "Blue Pick 1 center",
    "blue_pick_last": "Blue Pick 5 center",
    "red_pick_first": "Red Pick 1 center",
    "red_pick_last": "Red Pick 5 center",
}

POINT_DESCRIPTIONS_CN = {
    "blue_ban_first": "蓝方第 1 个 Ban 位中心",
    "blue_ban_last": "蓝方第 5 个 Ban 位中心",
    "red_ban_first": "红方第 1 个 Ban 位中心",
    "red_ban_last": "红方第 5 个 Ban 位中心",
    "blue_pick_first": "蓝方第 1 个 Pick 位中心",
    "blue_pick_last": "蓝方第 5 个 Pick 位中心",
    "red_pick_first": "红方第 1 个 Pick 位中心",
    "red_pick_last": "红方第 5 个 Pick 位中心",
}


def beep():
    """
    Windows 下给一个短提示音。
    其他系统没有 winsound，就静默跳过。
    """
    try:
        import winsound
        winsound.Beep(900, 80)
    except Exception:
        pass


def build_slots_by_centers(
    first: Tuple[int, int],
    last: Tuple[int, int],
    count: int,
    width: int,
    height: int,
) -> List[Dict[str, int]]:
    x1, y1 = first
    x2, y2 = last

    slots = []

    for i in range(count):
        if count == 1:
            cx, cy = x1, y1
        else:
            t = i / (count - 1)
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)

        slots.append({
            "left": int(cx - width / 2),
            "top": int(cy - height / 2),
            "width": width,
            "height": height,
        })

    return slots


def draw_slots(frame, slots, color, label_prefix):
    for idx, slot in enumerate(slots, start=1):
        x = slot["left"]
        y = slot["top"]
        w = slot["width"]
        h = slot["height"]

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame,
            f"{label_prefix}{idx}",
            (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    print("\n=== LOL BP 坐标校准工具 ===")
    print("请先打开 LOL Ban/Pick 界面。")
    print("然后按照提示依次点击对应位置的中心点。")
    print("按 z 撤销上一个点，按 q 退出。\n")

    print("需要点击 8 个点：")
    for i, label in enumerate(POINT_LABELS, start=1):
        print(f"{i}. {POINT_DESCRIPTIONS_CN[label]}")

    print("\n建议：点击头像/槽位的正中心，不要点边框。")

    ban_size_input = input("\nBan 位裁剪大小，默认 52，直接回车即可：").strip()
    pick_size_input = input("Pick 位裁剪大小，默认 82，直接回车即可：").strip()

    ban_size = int(ban_size_input) if ban_size_input else 52
    pick_size = int(pick_size_input) if pick_size_input else 82

    capture = ScreenCapture()
    frame = capture.capture()

    h, w = frame.shape[:2]

    max_display_w = 1280
    max_display_h = 720
    scale = min(max_display_w / w, max_display_h / h, 1.0)

    display_w = int(w * scale)
    display_h = int(h * scale)

    display_base = cv2.resize(frame, (display_w, display_h))
    clicked_points: List[Tuple[int, int]] = []

    window_name = "LOL BP Calibration - click points"

    flash_until = 0.0
    last_clicked_display_point = None

    def redraw():
        nonlocal flash_until, last_clicked_display_point

        display = display_base.copy()



        # 画已点击的点
        for idx, (ox, oy) in enumerate(clicked_points):
            dx = int(ox * scale)
            dy = int(oy * scale)

            # 外圈
            cv2.circle(display, (dx, dy), 14, (0, 0, 0), 4)
            cv2.circle(display, (dx, dy), 13, (0, 255, 0), 3)

            # 中心点
            cv2.circle(display, (dx, dy), 4, (0, 255, 0), -1)

            # 十字线
            cv2.line(display, (dx - 20, dy), (dx + 20, dy), (0, 255, 0), 2)
            cv2.line(display, (dx, dy - 20), (dx, dy + 20), (0, 255, 0), 2)

            # 数字
            cv2.putText(
                display,
                str(idx + 1),
                (dx + 16, dy - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                3,
                cv2.LINE_AA,
            )

       


        # 点击后的短暂闪烁反馈
        if last_clicked_display_point is not None and time.time() < flash_until:
            fx, fy = last_clicked_display_point
            cv2.circle(display, (fx, fy), 35, (0, 255, 255), 4)
            cv2.putText(
                display,
                "CLICKED!",
                (fx + 25, fy + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow(window_name, display)

    def on_mouse(event, x, y, flags, param):
        nonlocal flash_until, last_clicked_display_point

        if event == cv2.EVENT_LBUTTONDOWN:
            if len(clicked_points) >= len(POINT_LABELS):
                return

            ox = int(x / scale)
            oy = int(y / scale)

            clicked_points.append((ox, oy))

            label = POINT_LABELS[len(clicked_points) - 1]
            print(f"已记录 {len(clicked_points)}/8：{POINT_DESCRIPTIONS_CN[label]} -> ({ox}, {oy})")

            last_clicked_display_point = (x, y)
            flash_until = time.time() + 0.25

            beep()
            redraw()

    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, on_mouse)
    redraw()

    while True:
        key = cv2.waitKey(30) & 0xFF

        # 为了让 CLICKED 闪烁能刷新
        if time.time() < flash_until:
            redraw()

        if key == ord("q"):
            print("已退出校准。")
            cv2.destroyAllWindows()
            return

        if key == ord("z"):
            if clicked_points:
                removed = clicked_points.pop()
                print(f"撤销点：{removed}")
                beep()
                redraw()

        if len(clicked_points) >= len(POINT_LABELS):
            print("\n8 个点已记录完成，按任意键保存。")
            cv2.waitKey(0)
            break

    cv2.destroyAllWindows()

    point_map = dict(zip(POINT_LABELS, clicked_points))

    layout = {
        "blue_bans": build_slots_by_centers(
            point_map["blue_ban_first"],
            point_map["blue_ban_last"],
            count=5,
            width=ban_size,
            height=ban_size,
        ),
        "red_bans": build_slots_by_centers(
            point_map["red_ban_first"],
            point_map["red_ban_last"],
            count=5,
            width=ban_size,
            height=ban_size,
        ),
        "blue_picks": build_slots_by_centers(
            point_map["blue_pick_first"],
            point_map["blue_pick_last"],
            count=5,
            width=pick_size,
            height=pick_size,
        ),
        "red_picks": build_slots_by_centers(
            point_map["red_pick_first"],
            point_map["red_pick_last"],
            count=5,
            width=pick_size,
            height=pick_size,
        ),
    }

    with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)

    preview = frame.copy()

    draw_slots(preview, layout["blue_bans"], (255, 0, 0), "BB")
    draw_slots(preview, layout["red_bans"], (0, 0, 255), "RB")
    draw_slots(preview, layout["blue_picks"], (255, 255, 0), "BP")
    draw_slots(preview, layout["red_picks"], (0, 255, 255), "RP")

    preview_path = DEBUG_DIR / "layout_preview.png"
    cv2.imwrite(str(preview_path), preview)

    print("\n校准完成。")
    print(f"坐标已保存到：{LAYOUT_FILE}")
    print(f"预览图已保存到：{preview_path}")
    print("请打开 layout_preview.png 检查框是否套住 Ban/Pick 位置。")


if __name__ == "__main__":
    main()