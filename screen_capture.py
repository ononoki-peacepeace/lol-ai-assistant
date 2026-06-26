from typing import Dict

import mss
import numpy as np
import cv2

from config import SCREEN_REGION


class ScreenCapture:
    """
    使用 mss 截取屏幕。
    """

    def __init__(self, region: Dict[str, int] | None = None):
        self.region = region or SCREEN_REGION

    def capture(self) -> np.ndarray:
        """
        截取屏幕，返回 OpenCV BGR 图像。
        """
        with mss.mss() as sct:
            img = sct.grab(self.region)
            frame = np.array(img)

        # mss 返回 BGRA，OpenCV 常用 BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    @staticmethod
    def crop(frame: np.ndarray, slot: Dict[str, int]) -> np.ndarray:
        """
        根据坐标裁剪图像。
        """
        left = slot["left"]
        top = slot["top"]
        width = slot["width"]
        height = slot["height"]

        return frame[top:top + height, left:left + width]