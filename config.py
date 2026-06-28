from pathlib import Path
import json
import os


# =========================
# 基础路径
# =========================

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_env_file(env_path: Path | None = None):
    if env_path is None:
        env_path = BASE_DIR / ".env"

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
RULES_DIR = BASE_DIR / "rules"
CONFIGS_DIR = BASE_DIR / "configs"
CHARACTERS_DIR = BASE_DIR / "characters"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
BP_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "bp"
RAW_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "raw"
DEBUG_OUTPUT_DIR = BASE_DIR / "debug_output"
CHAMPION_STRENGTH_PATH = BP_KNOWLEDGE_DIR / "champion_strength.json"
TEAM_COMBOS_PATH = BP_KNOWLEDGE_DIR / "team_combos.json"

# =========================
# 资源路径
# =========================

CHAMPION_ICON_DIR = ASSETS_DIR / "champions"
EMPTY_SLOT_TEMPLATE_DIR = ASSETS_DIR / "empty_slots"

CHAMPIONS_PATH = DATA_DIR / "champions.json"
CHAMPION_TAGS_PATH = DATA_DIR / "champion_tags.json"
LAYOUT_PATH = DATA_DIR / "layout.json"

PICK_RULES_PATH = RULES_DIR / "bp" / "pick_rules.json"

COUNTERS_PATH = BP_KNOWLEDGE_DIR / "counters.json"
team_combo_PATH = BP_KNOWLEDGE_DIR / "team_combo.json"
COMPOSITIONS_PATH = BP_KNOWLEDGE_DIR / "compositions.json"

LLM_CONFIG_PATH = CONFIGS_DIR / "llm_config.json"


# =========================
# 兼容旧代码的别名
# 旧文件如果 import 这些名字，也不会报错
# =========================

CHAMPION_DIR = CHAMPION_ICON_DIR
CHAMPIONS_FILE = CHAMPIONS_PATH
CHAMPION_TAGS_FILE = CHAMPION_TAGS_PATH
LAYOUT_FILE = LAYOUT_PATH

EMPTY_SLOT_DIR = EMPTY_SLOT_TEMPLATE_DIR
EMPTY_SLOT_TEMPLATE_PATH = EMPTY_SLOT_TEMPLATE_DIR

RULES_PATH = RULES_DIR
BP_RULES_PATH = RULES_DIR / "bp"

OUTPUT_DIR = DEBUG_OUTPUT_DIR
DEBUG_DIR = DEBUG_OUTPUT_DIR


# =========================
# 截图相关配置
# =========================

# None 表示使用 screen_capture.py 里的默认全屏逻辑。
# 如果你的 screen_capture.py 直接 mss.grab(SCREEN_REGION)，None 可能不行；
# 那就改成类似：
# SCREEN_REGION = {"left": 0, "top": 0, "width": 1920, "height": 1080}
SCREEN_REGION = None

# 旧代码 main.py 可能 import CAPTURE_INTERVAL
CAPTURE_INTERVAL = 1.0

# 新代码也可以用 WATCH_INTERVAL
WATCH_INTERVAL = CAPTURE_INTERVAL

DEFAULT_LAYOUT_PATH = DATA_DIR / "default_layout_1280x720.json"

# =========================
# 英雄识别相关参数
# =========================

# 英雄匹配阈值
MATCH_THRESHOLD = 0.72

# Top1 和 Top2 分数差距太小时，认为不够确定
MATCH_GAP_THRESHOLD = 0.08

# 空位模板匹配阈值
EMPTY_SLOT_THRESHOLD = 0.70

# 空位分数比英雄分数高多少时，判定为空位
EMPTY_SLOT_MARGIN = 0.03

# 连续多少帧一致才确认，后续稳定识别用
CONFIRM_FRAMES = 3

# 模板统一尺寸
TEMPLATE_SIZE = 96
BAN_TEMPLATE_SIZE = 40
# 有些旧代码可能用这个名字
IMAGE_SIZE = TEMPLATE_SIZE


# =========================
# BP / 位置相关
# =========================

ROLE_MAP = {
    "top": "上单",
    "jungle": "打野",
    "jg": "打野",
    "mid": "中单",
    "middle": "中单",
    "adc": "下路",
    "bot": "下路",
    "bottom": "下路",
    "support": "辅助",
    "sup": "辅助",
}


SIDE_MAP = {
    "blue": "蓝方",
    "red": "红方",
}


# =========================
# Riot API 相关
# 暂时不用也没事，留着兼容 analyze-player
# =========================

RIOT_API_KEY = os.environ.get("RIOT_API_KEY", "")

# 常见大区配置，后面你可以按实际改
RIOT_PLATFORM = "HN1"
RIOT_REGION = "ASIA"
# 兼容旧 riot_api.py 使用的名字
PLATFORM_ROUTE = RIOT_PLATFORM
REGIONAL_ROUTE = RIOT_REGION

# =========================
# LLM / AI 相关默认值
# 实际优先读取 configs/llm_config.json
# =========================

DEFAULT_LLM_CONFIG = {
    "provider": "ollama",
    "model": "qwen2.5:0.5b",
    "base_url": "http://127.0.0.1:11434",
    "stream": False,
    "max_tokens": 400,
    "temperature": 0.7,
    "character_card": "default_assistant",
}


# =========================
# 通用 JSON 工具函数
# =========================

def load_json(path: Path, default=None):
    """
    读取 JSON 文件。
    如果文件不存在或解析失败，返回 default。
    """
    if default is None:
        default = {}

    path = Path(path)

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[JSON 解析失败] {path}")
        print(f"错误信息: {e}")
        return default


def save_json(path: Path, data, indent: int = 2):
    """
    保存 JSON 文件，自动创建父目录。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# =========================
# layout 相关
# =========================

def load_layout():
    """
    优先读取默认 1280x720 客户端布局。
    如果没有默认布局，再读取手动校准 layout。
    """
    if DEFAULT_LAYOUT_PATH.exists():
        print(f"已加载默认布局：{DEFAULT_LAYOUT_PATH}")
        return load_json(DEFAULT_LAYOUT_PATH, default={})

    if LAYOUT_PATH.exists():
        print(f"已加载校准布局：{LAYOUT_PATH}")
        return load_json(LAYOUT_PATH, default={})

    print("没有找到布局文件。")
    return {}


def save_layout(layout: dict):
    """
    保存 BP 校准坐标。
    """
    save_json(LAYOUT_PATH, layout)


# =========================
# LLM config 相关
# =========================

def load_llm_config():
    """
    读取 LLM 配置。
    """
    config = DEFAULT_LLM_CONFIG.copy()
    user_config = load_json(LLM_CONFIG_PATH, default={})
    config.update(user_config)
    return config


# =========================
# 初始化目录
# =========================

def ensure_dirs():
    """
    确保项目常用目录存在。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    BP_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    CHAMPION_ICON_DIR.mkdir(parents=True, exist_ok=True)
    EMPTY_SLOT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    BP_RULES_PATH.mkdir(parents=True, exist_ok=True)


ensure_dirs()