import json
from pathlib import Path

from jsonschema import Draft7Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_DIR = PROJECT_ROOT / "knowledge" / "schemas"
PROPOSAL_DIR = PROJECT_ROOT / "knowledge" / "proposals"


PROPOSAL_SCHEMA_MAP = {
    "counters_candidates.json": "counters.schema.json",
    "champion_strength_candidates.json": "champion_strength.schema.json",
    "team_combo_candidates.json": "team_combo.schema.json",
}


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def format_path(error_path):
    if not error_path:
        return "$"

    result = "$"
    for part in error_path:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def validate_file(proposal_path: Path, schema_path: Path) -> bool:
    print("\n" + "=" * 70)
    print(f"校验文件：{proposal_path.relative_to(PROJECT_ROOT)}")
    print(f"使用 schema：{schema_path.relative_to(PROJECT_ROOT)}")

    try:
        data = load_json(proposal_path)
    except Exception as e:
        print(f"[失败] JSON 读取失败：{e}")
        return False

    try:
        schema = load_json(schema_path)
    except Exception as e:
        print(f"[失败] Schema 读取失败：{e}")
        return False

    validator = Draft7Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda e: list(e.path)
    )

    if not errors:
        count = len(data) if isinstance(data, list) else "unknown"
        print(f"[通过] 共 {count} 条候选记录。")
        return True

    print(f"[失败] 发现 {len(errors)} 个格式问题：")

    for i, error in enumerate(errors, start=1):
        path = format_path(error.path)
        print(f"\n{i}. 位置：{path}")
        print(f"   问题：{error.message}")

    return False


def ensure_empty_proposal_files():
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)

    for proposal_file in PROPOSAL_SCHEMA_MAP:
        path = PROPOSAL_DIR / proposal_file
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")
            print(f"[创建] {path.relative_to(PROJECT_ROOT)}")


def main():
    ensure_empty_proposal_files()

    all_passed = True

    for proposal_file, schema_file in PROPOSAL_SCHEMA_MAP.items():
        proposal_path = PROPOSAL_DIR / proposal_file
        schema_path = SCHEMA_DIR / schema_file

        if not schema_path.exists():
            print(f"[失败] 找不到 schema：{schema_path}")
            all_passed = False
            continue

        ok = validate_file(proposal_path, schema_path)
        if not ok:
            all_passed = False

    print("\n" + "=" * 70)

    if all_passed:
        print("全部 proposals 校验通过。")
    else:
        print("存在校验失败的 proposals，请先修复。")


if __name__ == "__main__":
    main()