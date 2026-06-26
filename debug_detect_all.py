import cv2

from screen_capture import ScreenCapture
from champion_detector import ChampionDetector
from config import (
    BLUE_BAN_SLOTS,
    RED_BAN_SLOTS,
    BLUE_PICK_SLOTS,
    RED_PICK_SLOTS,
)


def get_top_matches(detector, crop_img, top_k=3):
    """
    打印某个槽位最像的前几个英雄，方便调试阈值。
    """
    results = []

    for champion_name, template in detector.templates.items():
        score = detector._match_score(crop_img, template)
        results.append((champion_name, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def test_group(frame, capture, detector, slots, group_name):
    print(f"\n=== {group_name} ===")

    for i, slot in enumerate(slots, start=1):
        crop = capture.crop(frame, slot)

        detected = detector.detect_champion(crop)
        top_matches = get_top_matches(detector, crop, top_k=3)

        if detected is None:
            print(f"{group_name}_{i}: 未识别")
        else:
            champion, score = detected
            print(f"{group_name}_{i}: 识别为 {champion}, 分数 {score:.3f}")

        print("  Top3:", ", ".join([f"{name}:{score:.3f}" for name, score in top_matches]))


def main():
    capture = ScreenCapture()
    detector = ChampionDetector()

    if not detector.templates:
        print("没有加载到任何英雄模板。请先把英雄头像放到 assets/champions/")
        return

    frame = capture.capture()

    test_group(frame, capture, detector, BLUE_BAN_SLOTS, "blue_bans")
    test_group(frame, capture, detector, RED_BAN_SLOTS, "red_bans")
    test_group(frame, capture, detector, BLUE_PICK_SLOTS, "blue_picks")
    test_group(frame, capture, detector, RED_PICK_SLOTS, "red_picks")


if __name__ == "__main__":
    main()