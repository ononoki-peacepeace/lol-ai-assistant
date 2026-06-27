from pathlib import Path
import json


# =========================
# 基础路径
# =========================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
RULES_DIR = BASE_DIR / "rules"
CONFIGS_DIR = BASE_DIR / "configs"
CHARACTERS_DIR = BASE_DIR / "characters"
DEBUG_OUTPUT_DIR = BASE_DIR / "debug_output"


# =========================
# 资源路径
# =========================

CHAMPION_ICON_DIR = ASSETS_DIR / "champions"
EMPTY_SLOT_TEMPLATE_DIR = ASSETS_DIR / "empty_slots"

CHAMPIONS_PATH = DATA_DIR / "champions.json"
CHAMPION_TAGS_PATH = DATA_DIR / "champion_tags.json"
LAYOUT_PATH = DATA_DIR / "layout.json"

PICK_RULES_PATH = RULES_DIR / "bp" / "pick_rules.json"

LLM_CONFIG_PATH = CONFIGS_DIR / "llm_config.json"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
BP_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "bp"

COUNTERS_PATH = BP_KNOWLEDGE_DIR / "counters.json"
SYNERGIES_PATH = BP_KNOWLEDGE_DIR / "synergies.json"
COMPOSITIONS_PATH = BP_KNOWLEDGE_DIR / "compositions.json"

# =========================
# 兼容旧代码的别名
# 如果之前某些文件用的是这些名字，就不会报错
# =========================

CHAMPION_DIR = CHAMPION_ICON_DIR
CHAMPIONS_FILE = CHAMPIONS_PATH
CHAMPION_TAGS_FILE = CHAMPION_TAGS_PATH
LAYOUT_FILE = LAYOUT_PATH


# =========================
# 识别相关参数
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

# watch-bp 截图间隔，单位秒
WATCH_INTERVAL = 1.0


# =========================
# 位置映射
# =========================

ROLE_MAP = {
    "top": "上单",
    "jungle": "打野",
    "jg": "打野",
    "mid": "中单",
    "middle": "中单",
    "adc": "下路",
    "bot": "下路",
    "support": "辅助",
    "sup": "辅助",
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

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[JSON 解析失败] {path}")
        print(f"错误信息: {e}")
        return default


def save_json(path: Path, data, indent: int = 2):
    """
    保存 JSON 文件，自动创建父目录。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


# =========================
# layout 相关
# =========================

def load_layout():
    """
    读取 BP 校准坐标。
    注意：这里不主动 print，避免 import config 时产生多余输出。
    """
    return load_json(LAYOUT_PATH, default={})


def save_layout(layout: dict):
    """
    保存 BP 校准坐标。
    """
    save_json(LAYOUT_PATH, layout)


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
    DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAMPION_ICON_DIR.mkdir(parents=True, exist_ok=True)
    EMPTY_SLOT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    BP_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

ensure_dirs()