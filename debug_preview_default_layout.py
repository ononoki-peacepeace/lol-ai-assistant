from pathlib import Path

import cv2

from config import DEFAULT_LAYOUT_PATH, load_json
from screen_capture import ScreenCapture


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR / "debug_output" / "default_layout_preview.png"


def draw_points(img, points, color, label_prefix):
    for idx, point in enumerate(points, start=1):
        x, y = point
        cv2.circle(img, (x, y), 12, color, 2)
        cv2.putText(
            img,
            f"{label_prefix}{idx}",
            (x + 14, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )


def main():
    layout = load_json(DEFAULT_LAYOUT_PATH, default={})

    capture = ScreenCapture()
    img = capture.capture()

    print(f"截图尺寸: {img.shape[1]} x {img.shape[0]}")
    print(f"布局文件: {DEFAULT_LAYOUT_PATH}")

    draw_points(img, layout.get("blue_picks", []), (255, 0, 0), "B")
    draw_points(img, layout.get("red_picks", []), (0, 0, 255), "R")
    draw_points(img, layout.get("blue_bans", []), (255, 255, 0), "BB")
    draw_points(img, layout.get("red_bans", []), (0, 255, 255), "RB")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT_PATH), img)

    print(f"已保存预览图: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()