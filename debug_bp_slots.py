from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from config import load_layout
from screen_capture import ScreenCapture

try:
    from config import DEBUG_OUTPUT_DIR
except ImportError:
    DEBUG_OUTPUT_DIR = Path(__file__).resolve().parent / "debug_output"

try:
    from config import PICK_TEMPLATE_SIZE
except ImportError:
    PICK_TEMPLATE_SIZE = 96

try:
    from config import BAN_TEMPLATE_SIZE
except ImportError:
    BAN_TEMPLATE_SIZE = 64


ROOT_DIR = Path(__file__).resolve().parent


def scale_slot(slot: Any, layout: dict, frame):
    """
    根据 layout 的 base_width/base_height，把槽位坐标缩放到当前截图尺寸。
    支持：
    [x, y]
    [left, top, right, bottom]
    [left, top, width, height]
    {"center": [x, y]}
    {"x": x, "y": y}
    {"left": ..., "top": ..., "width": ..., "height": ...}
    """
    h, w = frame.shape[:2]

    base_width = layout.get("base_width") or w
    base_height = layout.get("base_height") or h

    sx = w / base_width
    sy = h / base_height

    if isinstance(slot, dict):
        if "center" in slot:
            x, y = slot["center"]
            return [round(x * sx), round(y * sy)]

        if "x" in slot and "y" in slot:
            return [round(slot["x"] * sx), round(slot["y"] * sy)]

        if all(k in slot for k in ["left", "top", "width", "height"]):
            left = round(slot["left"] * sx)
            top = round(slot["top"] * sy)
            width = round(slot["width"] * sx)
            height = round(slot["height"] * sy)
            return [left, top, width, height]

        return slot

    if not isinstance(slot, list):
        return slot

    if len(slot) == 2:
        x, y = slot
        return [round(x * sx), round(y * sy)]

    if len(slot) == 4:
        a, b, c, d = slot

        # 如果像 [left, top, right, bottom]
        if c > a and d > b:
            return [
                round(a * sx),
                round(b * sy),
                round(c * sx),
                round(d * sy),
            ]

        # 否则按 [left, top, width, height]
        return [
            round(a * sx),
            round(b * sy),
            round(c * sx),
            round(d * sy),
        ]

    return slot


def get_crop_box(frame, slot, crop_size: int):
    """
    返回 left, top, right, bottom
    """
    h, w = frame.shape[:2]

    if isinstance(slot, dict):
        if "center" in slot:
            slot = slot["center"]
        elif "x" in slot and "y" in slot:
            slot = [slot["x"], slot["y"]]
        elif all(k in slot for k in ["left", "top", "width", "height"]):
            left = int(slot["left"])
            top = int(slot["top"])
            right = left + int(slot["width"])
            bottom = top + int(slot["height"])
            return clamp_box(left, top, right, bottom, w, h)

    if len(slot) == 2:
        x, y = map(int, slot)
        half = crop_size // 2

        left = x - half
        top = y - half
        right = x + half
        bottom = y + half

        return clamp_box(left, top, right, bottom, w, h)

    if len(slot) == 4:
        a, b, c, d = map(int, slot)

        # [left, top, right, bottom]
        if c > a and d > b:
            left, top, right, bottom = a, b, c, d

        # [left, top, width, height]
        else:
            left, top, right, bottom = a, b, a + c, b + d

        return clamp_box(left, top, right, bottom, w, h)

    raise ValueError(f"不支持的 slot 格式: {slot}")


def clamp_box(left: int, top: int, right: int, bottom: int, width: int, height: int):
    left = max(0, left)
    top = max(0, top)
    right = min(width, right)
    bottom = min(height, bottom)

    return left, top, right, bottom


def crop_slot(frame, slot, crop_size: int):
    left, top, right, bottom = get_crop_box(frame, slot, crop_size)

    if right <= left or bottom <= top:
        return None, (left, top, right, bottom)

    return frame[top:bottom, left:right], (left, top, right, bottom)


def save_group(
    frame,
    overlay,
    layout: dict,
    output_dir: Path,
    group_name: str,
    slots: list,
    crop_size: int,
):
    group_dir = output_dir / group_name
    group_dir.mkdir(parents=True, exist_ok=True)

    for index, raw_slot in enumerate(slots, start=1):
        try:
            slot = scale_slot(raw_slot, layout, frame)
            crop, box = crop_slot(frame, slot, crop_size)

            left, top, right, bottom = box

            cv2.rectangle(
                overlay,
                (left, top),
                (right, bottom),
                (0, 255, 0),
                2,
            )

            cv2.putText(
                overlay,
                f"{group_name}_{index}",
                (left, max(0, top - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

            if crop is None or crop.size == 0:
                print(f"[WARN] 空裁剪：{group_name}_{index}, slot={raw_slot}, scaled={slot}, box={box}")
                continue

            filename = group_dir / f"{group_name}_{index}.png"
            cv2.imwrite(str(filename), crop)

            print(f"[OK] {group_name}_{index}: raw={raw_slot}, scaled={slot}, box={box}, file={filename}")

        except Exception as e:
            print(f"[ERROR] {group_name}_{index}: slot={raw_slot}, error={e}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ban-size",
        type=int,
        default=BAN_TEMPLATE_SIZE,
        help="ban 位裁剪尺寸，默认读取 config.BAN_TEMPLATE_SIZE",
    )

    parser.add_argument(
        "--pick-size",
        type=int,
        default=PICK_TEMPLATE_SIZE,
        help="pick 位裁剪尺寸，默认读取 config.PICK_TEMPLATE_SIZE",
    )

    parser.add_argument(
        "--prefix",
        default="bp_slots",
        help="输出目录前缀",
    )

    args = parser.parse_args()

    layout = load_layout()

    if not layout:
        print("[ERROR] 没有加载到 layout。请检查 data/default_layout_1280x720.json")
        return

    capture = ScreenCapture()
    frame = capture.capture()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(DEBUG_OUTPUT_DIR) / f"{args.prefix}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] frame size: {frame.shape[1]}x{frame.shape[0]}")
    print(f"[INFO] ban_size={args.ban_size}, pick_size={args.pick_size}")
    print(f"[INFO] output_dir={output_dir}")

    overlay = frame.copy()

    cv2.imwrite(str(output_dir / "full_frame.png"), frame)

    save_group(
        frame=frame,
        overlay=overlay,
        layout=layout,
        output_dir=output_dir,
        group_name="blue_bans",
        slots=layout.get("blue_bans", []),
        crop_size=args.ban_size,
    )

    save_group(
        frame=frame,
        overlay=overlay,
        layout=layout,
        output_dir=output_dir,
        group_name="red_bans",
        slots=layout.get("red_bans", []),
        crop_size=args.ban_size,
    )

    save_group(
        frame=frame,
        overlay=overlay,
        layout=layout,
        output_dir=output_dir,
        group_name="blue_picks",
        slots=layout.get("blue_picks", []),
        crop_size=args.pick_size,
    )

    save_group(
        frame=frame,
        overlay=overlay,
        layout=layout,
        output_dir=output_dir,
        group_name="red_picks",
        slots=layout.get("red_picks", []),
        crop_size=args.pick_size,
    )

    cv2.imwrite(str(output_dir / "overlay_slots.png"), overlay)

    print("\n[DONE] 已保存：")
    print(output_dir)
    print("\n重点查看：")
    print("- overlay_slots.png：整张图上的框")
    print("- blue_bans/*.png")
    print("- red_bans/*.png")


if __name__ == "__main__":
    main()