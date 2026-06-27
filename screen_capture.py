import cv2
import mss
import numpy as np

from config import SCREEN_REGION
from window_utils import get_lol_client_region


class ScreenCapture:
    def __init__(self, region=None, prefer_lol_window=True):
        self.region = region
        self.prefer_lol_window = prefer_lol_window

    def get_region(self):
        """
        优先截 LOL 客户端窗口。
        找不到 LOL 窗口时，退回 SCREEN_REGION。
        SCREEN_REGION 也为空时，截主屏幕。
        """
        if self.prefer_lol_window:
            lol_region = get_lol_client_region()
            if lol_region is not None:
                return lol_region

        if self.region is not None:
            return self.region

        if SCREEN_REGION is not None:
            return SCREEN_REGION

        return None

    def capture(self):
        """
        返回 BGR 图片。
        """
        region = self.get_region()

        with mss.mss() as sct:
            if region is None:
                monitor = sct.monitors[1]
                img = np.array(sct.grab(monitor))
            else:
                img = np.array(sct.grab(region))

        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def save_debug(self, path):
        img = self.capture()
        cv2.imwrite(str(path), img)
        return img