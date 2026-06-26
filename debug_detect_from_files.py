from pathlib import Path
import cv2

from config import BASE_DIR
from champion_detector import ChampionDetector


DEBUG_DIR = BASE_DIR / "debug_output"

GROUPS = [
    "blue_bans",
    "red_bans",
    "blue_picks",
    "red_picks",
]


def get_top_matches(detector, crop_img, top_k=5):
    results = []

    for champion_name, template in detector.templates.items():
        score = detector._match_score(crop_img, template)
        results.append((champion_name, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def test_image(detector, image_path: Path):
    img = cv2.imread(str(image_path))

    if img is None:
        print(f"{image_path.name}: 读取失败")
        return

    detected = detector.detect_champion(img)
    top_matches = get_top_matches(detector, img, top_k=5)

    if detected is None:
        print(f"{image_path.name}: 未识别")
    else:
        champion, score = detected
        print(f"{image_path.name}: 识别为 {champion}, 分数 {score:.3f}")

    print("  Top5:", ", ".join([f"{name}:{score:.3f}" for name, score in top_matches]))


def main():
    detector = ChampionDetector()

    if not detector.templates:
        print("没有加载到英雄模板，请检查 assets/champions/")
        return

    for group in GROUPS:
        group_dir = DEBUG_DIR / group

        if not group_dir.exists():
            continue

        print(f"\n=== {group} ===")

        image_paths = sorted(group_dir.glob("*.png"))

        if not image_paths:
            print("没有 PNG 图片")
            continue

        for image_path in image_paths:
            test_image(detector, image_path)


if __name__ == "__main__":
    main()