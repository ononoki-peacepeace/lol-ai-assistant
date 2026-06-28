from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
CHAMPION_TAGS_PATH = ROOT_DIR / "data" / "champion_tags.json"


ROLE_CN_TO_KEY = {
    "上单": "top",
    "打野": "jungle",
    "中单": "mid",
    "下路": "adc",
    "辅助": "support",
}

ROLE_KEY_TO_CN = {
    "top": "上单",
    "jungle": "打野",
    "mid": "中单",
    "adc": "下路",
    "support": "辅助",
}

ROLE_ALIASES = {
    "top": "top",
    "上单": "top",
    "上路": "top",

    "jungle": "jungle",
    "jg": "jungle",
    "打野": "jungle",

    "mid": "mid",
    "middle": "mid",
    "中单": "mid",
    "中路": "mid",

    "adc": "adc",
    "bot": "adc",
    "bottom": "adc",
    "下路": "adc",
    "射手": "adc",

    "support": "support",
    "sup": "support",
    "辅助": "support",
}


ROLES = ["top", "jungle", "mid", "adc", "support"]


def load_json(path: Path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_role(tag: str) -> str | None:
    if not isinstance(tag, str):
        return None

    return ROLE_ALIASES.get(tag.strip())


def build_role_pools(champion_tags: dict) -> dict[str, list[str]]:
    """
    从 champion_tags.json 里构建各位置英雄池。

    champion_tags.json 示例：
    {
      "Aatrox": ["上单", "战士", "回复"],
      "LeeSin": ["打野", "战士", "突进"]
    }
    """
    pools = {role: [] for role in ROLES}

    for champion_id, tags in champion_tags.items():
        if not isinstance(tags, list):
            continue

        champion_roles = set()

        for tag in tags:
            role = normalize_role(tag)
            if role:
                champion_roles.add(role)

        for role in champion_roles:
            pools[role].append(champion_id)

    for role in ROLES:
        pools[role] = sorted(set(pools[role]))

    return pools


def validate_pools(pools: dict[str, list[str]]) -> None:
    missing = []

    for role in ROLES:
        if not pools.get(role):
            missing.append(role)

    if missing:
        role_names = [ROLE_KEY_TO_CN.get(role, role) for role in missing]
        raise RuntimeError(f"这些位置没有可用英雄池：{role_names}，请检查 data/champion_tags.json")


def pick_unique(pool: list[str], used: set[str]) -> str | None:
    candidates = [champ for champ in pool if champ not in used]

    if not candidates:
        return None

    champion = random.choice(candidates)
    used.add(champion)
    return champion


def random_partial_team(
    pools: dict[str, list[str]],
    used: set[str],
    min_count: int,
    max_count: int,
) -> dict[str, str]:
    role_count = random.randint(min_count, max_count)
    selected_roles = random.sample(ROLES, role_count)

    picks = {}

    for role in selected_roles:
        champion = pick_unique(pools[role], used)
        if champion:
            picks[role] = champion

    return picks


def generate_bans(
    pools: dict[str, list[str]],
    used: set[str],
    min_count: int = 0,
    max_count: int = 10,
) -> list[str]:
    all_champions = []

    for pool in pools.values():
        all_champions.extend(pool)

    all_champions = sorted(set(all_champions))

    ban_count = random.randint(min_count, max_count)
    candidates = [champ for champ in all_champions if champ not in used]

    bans = random.sample(candidates, min(ban_count, len(candidates)))

    for champion in bans:
        used.add(champion)

    return bans


def generate_one(index: int, pools: dict[str, list[str]]) -> dict:
    used = set()

    bans = generate_bans(
        pools=pools,
        used=used,
        min_count=0,
        max_count=10,
    )

    blue_picks = random_partial_team(
        pools=pools,
        used=used,
        min_count=1,
        max_count=4,
    )

    red_picks = random_partial_team(
        pools=pools,
        used=used,
        min_count=1,
        max_count=5,
    )

    target_side = random.choice(["blue", "red"])
    target_role = random.choice(ROLES)

    return {
        "id": f"synthetic_bp_{index:05d}",
        "type": "synthetic_bp_scenario",
        "target_side": target_side,
        "target_role": target_role,
        "target_role_cn": ROLE_KEY_TO_CN[target_role],
        "bans": bans,
        "blue_picks": blue_picks,
        "red_picks": red_picks,
        "task": "根据当前 BP 局面，判断应该搜索哪些 counter、英雄强度、阵容配合与阵容缺口知识。"
    }


def print_pool_summary(pools: dict[str, list[str]]) -> None:
    print("[英雄池统计]")

    for role in ROLES:
        print(f"- {ROLE_KEY_TO_CN[role]}：{len(pools[role])} 个")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="生成多少个随机 BP 场景",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子，方便复现",
    )

    parser.add_argument(
        "--out",
        default="knowledge/scenarios/random_bp_scenarios.jsonl",
        help="输出 JSONL 文件",
    )

    parser.add_argument(
        "--print-pools",
        action="store_true",
        help="打印每个位置的英雄池",
    )

    args = parser.parse_args()

    random.seed(args.seed)

    champion_tags = load_json(CHAMPION_TAGS_PATH, default={})
    pools = build_role_pools(champion_tags)

    validate_pools(pools)
    print_pool_summary(pools)

    if args.print_pools:
        print("\n[详细英雄池]")
        for role in ROLES:
            print(f"\n{ROLE_KEY_TO_CN[role]}：")
            print(", ".join(pools[role]))

    out_path = ROOT_DIR / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for i in range(1, args.count + 1):
            item = generate_one(i, pools)
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n[完成] 已生成 {args.count} 个随机 BP 场景：{out_path}")


if __name__ == "__main__":
    main()