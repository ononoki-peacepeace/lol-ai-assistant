import os
import cv2

from screen_capture import ScreenCapture
from config import (
    BLUE_BAN_SLOTS,
    RED_BAN_SLOTS,
    BLUE_PICK_SLOTS,
    RED_PICK_SLOTS,
)

DEBUG_DIR = "debug_output"


def save_slots(frame, capture, slots, group_name):
    group_dir = os.path.join(DEBUG_DIR, group_name)
    os.makedirs(group_dir, exist_ok=True)

    for i, slot in enumerate(slots):
        crop = capture.crop(frame, slot)
        path = os.path.join(group_dir, f"{group_name}_{i + 1}.png")
        cv2.imwrite(path, crop)
        print(f"保存：{path}")


def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)

    capture = ScreenCapture()
    frame = capture.capture()

    full_path = os.path.join(DEBUG_DIR, "full_screen.png")
    cv2.imwrite(full_path, frame)
    print(f"保存完整截图：{full_path}")

    save_slots(frame, capture, BLUE_BAN_SLOTS, "blue_bans")
    save_slots(frame, capture, RED_BAN_SLOTS, "red_bans")
    save_slots(frame, capture, BLUE_PICK_SLOTS, "blue_picks")
    save_slots(frame, capture, RED_PICK_SLOTS, "red_picks")


if __name__ == "__main__":
    main()