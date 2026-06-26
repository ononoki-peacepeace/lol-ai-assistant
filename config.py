import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")

# Riot API 路由配置
# account-v1 和 match-v5 使用 regional route，例如 asia / americas / europe
# LOL 服务器平台用 platform route，例如 kr / jp1 / na1 / euw1
REGIONAL_ROUTE = os.getenv("REGIONAL_ROUTE", "asia")
PLATFORM_ROUTE = os.getenv("PLATFORM_ROUTE", "kr")

MATCH_COUNT = int(os.getenv("MATCH_COUNT", "20"))

# 截图间隔，单位秒
CAPTURE_INTERVAL = float(os.getenv("CAPTURE_INTERVAL", "1.0"))

# 模板匹配阈值，越高越严格
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.58"))

# 英雄头像模板目录
CHAMPION_TEMPLATE_DIR = BASE_DIR / "assets" / "champions"
EMPTY_SLOT_TEMPLATE_DIR = BASE_DIR / "assets" / "empty_slots"

# 空位识别阈值
EMPTY_SLOT_THRESHOLD = 0.70

# 如果空位分数接近或高于英雄分数，就优先认为是空位
EMPTY_SLOT_MARGIN = 0.03
DATA_DIR = BASE_DIR / "data"
CHAMPIONS_JSON = DATA_DIR / "champions.json"
# 第一版：手动配置 BP 区域坐标
# 坐标格式：{"left": x, "top": y, "width": w, "height": h}
# 你需要根据自己的 LOL 客户端截图调整这些坐标
SCREEN_REGION = {
    "left": int(os.getenv("SCREEN_LEFT", "0")),
    "top": int(os.getenv("SCREEN_TOP", "0")),
    "width": int(os.getenv("SCREEN_WIDTH", "1920")),
    "height": int(os.getenv("SCREEN_HEIGHT", "1080")),
}

# Ban / Pick 裁剪区域。
# 第一版先写占位坐标，你后面需要用截图工具测量。
# 坐标是相对于整张截图的像素坐标。
BLUE_BAN_SLOTS = [
    {"left": 250, "top": 720, "width": 48, "height": 48},
    {"left": 310, "top": 720, "width": 48, "height": 48},
    {"left": 370, "top": 720, "width": 48, "height": 48},
    {"left": 430, "top": 720, "width": 48, "height": 48},
    {"left": 490, "top": 720, "width": 48, "height": 48},
]

RED_BAN_SLOTS = [
    {"left": 1380, "top": 720, "width": 48, "height": 48},
    {"left": 1440, "top": 720, "width": 48, "height": 48},
    {"left": 1500, "top": 720, "width": 48, "height": 48},
    {"left": 1560, "top": 720, "width": 48, "height": 48},
    {"left": 1620, "top": 720, "width": 48, "height": 48},
]

BLUE_PICK_SLOTS = [
    {"left": 150, "top": 180, "width": 80, "height": 80},
    {"left": 150, "top": 290, "width": 80, "height": 80},
    {"left": 150, "top": 400, "width": 80, "height": 80},
    {"left": 150, "top": 510, "width": 80, "height": 80},
    {"left": 150, "top": 620, "width": 80, "height": 80},
]

RED_PICK_SLOTS = [
    {"left": 1690, "top": 180, "width": 80, "height": 80},
    {"left": 1690, "top": 290, "width": 80, "height": 80},
    {"left": 1690, "top": 400, "width": 80, "height": 80},
    {"left": 1690, "top": 510, "width": 80, "height": 80},
    {"left": 1690, "top": 620, "width": 80, "height": 80},
]

import json

LAYOUT_FILE = BASE_DIR / "data" / "layout.json"


def load_layout_from_file():
    """
    如果 data/layout.json 存在，就用校准后的坐标覆盖默认坐标。
    """
    if not LAYOUT_FILE.exists():
        return None

    try:
        with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
            layout = json.load(f)

        required_keys = [
            "blue_bans",
            "red_bans",
            "blue_picks",
            "red_picks",
        ]

        for key in required_keys:
            if key not in layout:
                print(f"layout.json 缺少字段：{key}，将使用默认坐标。")
                return None

        print(f"已加载校准坐标：{LAYOUT_FILE}")
        return layout

    except Exception as e:
        print(f"读取 layout.json 失败，将使用默认坐标：{e}")
        return None


_user_layout = load_layout_from_file()

if _user_layout:
    BLUE_BAN_SLOTS = _user_layout["blue_bans"]
    RED_BAN_SLOTS = _user_layout["red_bans"]
    BLUE_PICK_SLOTS = _user_layout["blue_picks"]
    RED_PICK_SLOTS = _user_layout["red_picks"]