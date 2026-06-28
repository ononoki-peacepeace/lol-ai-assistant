from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

PROFILES_PATH = ROOT_DIR / "configs" / "llm_profiles.json"
ACTIVE_CONFIG_PATH = ROOT_DIR / "configs" / "llm_config.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "profile",
        nargs="?",
        help="要切换的 LLM profile，例如 deepseek / ollama"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用 profile"
    )

    args = parser.parse_args()

    data = load_json(PROFILES_PATH)
    profiles = data.get("profiles", {})

    if args.list:
        print("[可用 LLM profiles]")
        for name in profiles.keys():
            marker = " 默认" if name == data.get("default") else ""
            print(f"- {name}{marker}")
        return

    profile_name = args.profile or data.get("default")

    if profile_name not in profiles:
        raise ValueError(f"找不到 profile: {profile_name}")

    active_config = dict(profiles[profile_name])
    active_config["profile"] = profile_name

    write_json(ACTIVE_CONFIG_PATH, active_config)

    print(f"[完成] 已切换 LLM profile: {profile_name}")
    print(f"[写入] {ACTIVE_CONFIG_PATH}")
    print(json.dumps(active_config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()