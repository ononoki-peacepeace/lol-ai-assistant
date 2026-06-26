from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import (
    CHAMPION_TEMPLATE_DIR,
    MATCH_THRESHOLD,
)

# 下面这些配置如果 config.py 里没写，就使用默认值
try:
    from config import EMPTY_SLOT_TEMPLATE_DIR
except ImportError:
    EMPTY_SLOT_TEMPLATE_DIR = Path("assets") / "empty_slots"

try:
    from config import EMPTY_SLOT_THRESHOLD
except ImportError:
    EMPTY_SLOT_THRESHOLD = 0.70

try:
    from config import EMPTY_SLOT_MARGIN
except ImportError:
    EMPTY_SLOT_MARGIN = 0.03

try:
    from config import MATCH_GAP_THRESHOLD
except ImportError:
    MATCH_GAP_THRESHOLD = 0.04


class ChampionDetector:
    """
    英雄头像识别器。

    识别逻辑：
    1. 加载英雄头像模板 assets/champions/
    2. 加载空位模板 assets/empty_slots/
    3. 先判断当前槽位是不是空位
    4. 如果不是空位，再判断最像哪个英雄
    """

    def __init__(
        self,
        template_dir=CHAMPION_TEMPLATE_DIR,
        threshold: float = MATCH_THRESHOLD,
        image_size: int = 96,
        inner_circle_ratio: float = 0.38,
    ):
        self.template_dir = Path(template_dir)
        self.threshold = threshold
        self.image_size = image_size
        self.inner_circle_ratio = inner_circle_ratio

        self.mask = self._build_circle_mask(image_size, inner_circle_ratio)

        # 英雄模板
        self.templates = self._load_templates(self.template_dir)
        self.template_features = {
            name: self._extract_features(img)
            for name, img in self.templates.items()
        }

        if not self.templates:
            print(f"警告：没有加载到英雄头像模板，请检查目录：{self.template_dir}")

        # 空位模板
        self.empty_template_dir = Path(EMPTY_SLOT_TEMPLATE_DIR)
        self.empty_templates = self._load_templates(self.empty_template_dir)
        self.empty_template_features = {
            name: self._extract_features(img)
            for name, img in self.empty_templates.items()
        }

        if not self.empty_templates:
            print(f"警告：没有加载到空位模板，请检查目录：{self.empty_template_dir}")

    def _load_templates(self, template_dir: Path) -> Dict[str, np.ndarray]:
        templates: Dict[str, np.ndarray] = {}

        template_dir.mkdir(parents=True, exist_ok=True)

        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}

        for path in template_dir.iterdir():
            if path.suffix.lower() not in valid_exts:
                continue

            img = cv2.imread(str(path), cv2.IMREAD_COLOR)

            if img is None:
                print(f"无法读取模板：{path}")
                continue

            templates[path.stem] = img

        return templates

    @staticmethod
    def _center_crop_square(img: np.ndarray) -> np.ndarray:
        """
        把图片中心裁成正方形。
        """
        h, w = img.shape[:2]
        side = min(h, w)

        left = (w - side) // 2
        top = (h - side) // 2

        return img[top:top + side, left:left + side]

    @staticmethod
    def _build_circle_mask(size: int, ratio: float) -> np.ndarray:
        """
        创建中心圆形 mask，减少金色边框和黑色背景的影响。
        """
        mask = np.zeros((size, size), dtype=np.uint8)
        center = (size // 2, size // 2)
        radius = int(size * ratio)

        cv2.circle(mask, center, radius, 255, -1)
        return mask

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        统一裁剪和缩放。
        """
        square = self._center_crop_square(img)
        resized = cv2.resize(square, (self.image_size, self.image_size))
        return resized

    def _extract_features(self, img: np.ndarray) -> Dict[str, Any]:
        """
        提取图像特征：
        1. 灰度结构向量
        2. HSV 颜色直方图
        """
        processed = self._preprocess(img)

        # 灰度结构
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mask_bool = self.mask > 0
        gray_pixels = gray[mask_bool]

        gray_pixels = gray_pixels - gray_pixels.mean()
        norm = np.linalg.norm(gray_pixels)

        if norm < 1e-6:
            gray_vector = gray_pixels
        else:
            gray_vector = gray_pixels / norm

        # HSV 颜色直方图
        hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)

        hist = cv2.calcHist(
            [hsv],
            [0, 1],
            self.mask,
            [32, 32],
            [0, 180, 0, 256],
        )

        cv2.normalize(hist, hist)

        return {
            "gray_vector": gray_vector,
            "hist": hist,
        }

    @staticmethod
    def _score_features(
        crop_features: Dict[str, Any],
        template_features: Dict[str, Any],
    ) -> float:
        """
        计算两张图的相似度。
        """
        crop_gray = crop_features["gray_vector"]
        template_gray = template_features["gray_vector"]

        if crop_gray.shape != template_gray.shape:
            return 0.0

        # 灰度结构相似度
        ncc = float(np.dot(crop_gray, template_gray))
        gray_score = (ncc + 1.0) / 2.0
        gray_score = max(0.0, min(1.0, gray_score))

        # 颜色直方图相似度
        hist_corr = cv2.compareHist(
            crop_features["hist"],
            template_features["hist"],
            cv2.HISTCMP_CORREL,
        )
        hist_score = (hist_corr + 1.0) / 2.0
        hist_score = max(0.0, min(1.0, hist_score))

        # 综合分数
        score = 0.7 * gray_score + 0.3 * hist_score

        return float(score)

    def _match_score(self, crop_img: np.ndarray, template: np.ndarray) -> float:
        """
        兼容 debug_detect_from_files.py 里的 Top5 调试。
        """
        crop_features = self._extract_features(crop_img)
        template_features = self._extract_features(template)

        return self._score_features(crop_features, template_features)

    def _get_best_empty_score(self, crop_features: Dict[str, Any]) -> float:
        """
        计算当前槽位和空位模板的最高相似度。
        """
        if not self.empty_template_features:
            return 0.0

        best_empty_score = 0.0

        for empty_name, empty_features in self.empty_template_features.items():
            score = self._score_features(crop_features, empty_features)

            if score > best_empty_score:
                best_empty_score = score

        return best_empty_score

    def detect_champion(self, crop_img: np.ndarray) -> Optional[Tuple[str, float]]:
        """
        识别单个英雄头像。

        返回：
        ("Darius", 0.86)

        如果是空位、不确定、分数不够，则返回 None。
        """
        if crop_img is None or crop_img.size == 0:
            return None

        crop_features = self._extract_features(crop_img)

        # 1. 先判断是不是空位
        empty_score = self._get_best_empty_score(crop_features)

        # 2. 计算所有英雄分数
        scores: List[Tuple[str, float]] = []

        for champion_name, template_features in self.template_features.items():
            score = self._score_features(crop_features, template_features)
            scores.append((champion_name, score))

        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores:
            return None

        best_name, best_score = scores[0]

        if len(scores) >= 2:
            second_name, second_score = scores[1]
        else:
            second_name, second_score = None, 0.0

        gap = best_score - second_score

        # 3. 如果更像空位，就不要识别成英雄
        if empty_score >= EMPTY_SLOT_THRESHOLD and empty_score >= best_score - EMPTY_SLOT_MARGIN:
            return None

        # 4. 英雄分数太低，不确认
        if best_score < self.threshold:
            return None

        # 5. Top1 和 Top2 差距太小，不确认
        if gap < MATCH_GAP_THRESHOLD:
            return None

        return best_name, best_score

    def detect_slots(self, slot_images: List[np.ndarray]) -> List[Optional[str]]:
        """
        批量识别多个 BP 槽位。
        """
        results: List[Optional[str]] = []

        for img in slot_images:
            detected = self.detect_champion(img)

            if detected is None:
                results.append(None)
            else:
                champion_name, score = detected
                results.append(champion_name)

        return results