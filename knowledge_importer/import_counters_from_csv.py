from pathlib import Path
import csv
import json


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_CSV = BASE_DIR / "knowledge" / "raw" / "counters_sample.csv"
OUTPUT_JSON = BASE_DIR / "knowledge" / "bp" / "counters.json"


def clean(value):
    return (value or "").strip()


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"找不到输入文件: {INPUT_CSV}")

    counters = {}

    with open(INPUT_CSV, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            champion = clean(row.get("champion"))
            enemy = clean(row.get("enemy"))

            if not champion or not enemy:
                continue

            score = to_int(row.get("score"), 0)

            if score == 0:
                continue

            item = {
                "champion": enemy,
                "score": score,
                "role": clean(row.get("role")),
                "patch": clean(row.get("patch")),
                "rank": clean(row.get("rank")),
                "source": clean(row.get("source")),
                "win_rate": to_float(row.get("win_rate"), 0.0),
                "sample_size": to_int(row.get("sample_size"), 0),
                "confidence": clean(row.get("confidence")),
                "reason": clean(row.get("reason")),
            }

            if champion not in counters:
                counters[champion] = {
                    "good_against": [],
                    "bad_against": []
                }

            if score > 0:
                counters[champion]["good_against"].append(item)
            else:
                counters[champion]["bad_against"].append(item)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(counters, f, ensure_ascii=False, indent=2)

    print(f"导入完成: {OUTPUT_JSON}")
    print(f"英雄数量: {len(counters)}")

    total_good = sum(len(v["good_against"]) for v in counters.values())
    total_bad = sum(len(v["bad_against"]) for v in counters.values())

    print(f"克制关系: {total_good}")
    print(f"被克制关系: {total_bad}")


if __name__ == "__main__":
    main()