from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_proposal_from_text import call_llm, extract_json_array


ROOT_DIR = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict]:
    items = []

    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))

    return items


def build_prompt(scenario: dict) -> str:
    return f"""
你是英雄联盟 BP 知识库搜索规划器。

你不会直接编写结论，你只负责根据当前 BP 场景规划应该搜索哪些资料。

请输出 JSON 数组，每个元素是一个搜索任务。

允许的字段：
- name: 字符串，任务名
- kind: 只能是 "auto"、"counters"、"strength"、"team_combo"
- query: 英文搜索语句
- must_contain: 必须包含的英雄关键词，用逗号分隔
- source_name: 推荐来源，可选 "OP.GG"、"League of Graphs"、"U.GG"、"LoLalytics"、"Reddit SummonerSchool"
- reason: 为什么需要搜索这个任务

规划原则：
1. 如果某一路已经能推断出对线关系，优先搜索该对线的 counter 和 matchup。
2. 如果目标方还缺某个位置，搜索该位置的强势英雄、counter 英雄和适合当前阵容的英雄。
3. 如果已有英雄之间可能存在配合，搜索 team_combo。
4. counter / strength 优先使用数据站：OP.GG、League of Graphs、U.GG、LoLalytics。
5. team_combo 可以使用 Reddit SummonerSchool 或一般搜索。
6. 不要输出 shell 命令。
7. 不要输出解释文字，只输出 JSON 数组。
8. 每个场景最多输出 5 个搜索任务。
9. 查询语句尽量用英文英雄 ID 和英文位置，例如 "Aatrox top lane matchup counters win rate"。
10. 如果信息不足，也要输出最有价值的搜索任务。

当前 BP 场景：
{json.dumps(scenario, ensure_ascii=False, indent=2)}
""".strip()


def normalize_job(job: dict, index: int) -> dict:
    kind = job.get("kind", "auto")

    if kind not in {"auto", "counters", "strength", "team_combo"}:
        kind = "auto"

    return {
        "name": job.get("name") or f"planned-job-{index}",
        "kind": kind,
        "query": job.get("query", ""),
        "must_contain": job.get("must_contain", ""),
        "source_name": job.get("source_name", "OP.GG"),
        "reason": job.get("reason", "")
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        default="knowledge/scenarios/random_bp_scenarios.jsonl"
    )

    parser.add_argument(
        "--out",
        default="knowledge/search/planned_bp_search_jobs.json"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多读取多少个场景。0 表示不限制。"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    args = parser.parse_args()

    input_path = ROOT_DIR / args.input
    out_path = ROOT_DIR / args.out

    scenarios = read_jsonl(input_path)

    if args.limit > 0:
        scenarios = scenarios[:args.limit]

    all_jobs = []
    seen = set()

    for scenario_index, scenario in enumerate(scenarios, start=1):
        print("\n" + "=" * 80)
        print(f"[场景] {scenario.get('id')}")

        prompt = build_prompt(scenario)
        raw_output = call_llm(prompt)

        print("\n===== AI 搜索规划原始输出 =====")
        print(raw_output)

        try:
            jobs = extract_json_array(raw_output)
        except Exception as e:
            print(f"[失败] AI 输出不是合法 JSON：{e}")
            continue

        for job in jobs:
            if not isinstance(job, dict):
                continue

            normalized = normalize_job(job, len(all_jobs) + 1)

            if not normalized["query"]:
                continue

            key = (
                normalized["kind"],
                normalized["query"],
                normalized["must_contain"],
                normalized["source_name"]
            )

            if key in seen:
                continue

            seen.add(key)
            all_jobs.append(normalized)

    config = {
        "defaults": {
            "max_results_per_source": 3,
            "max_chars_per_result": 20000,
            "save_raw": True
        },
        "jobs": all_jobs
    }

    print("\n" + "=" * 80)
    print(f"[完成] 生成搜索任务数：{len(all_jobs)}")

    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"[输出] {out_path}")


if __name__ == "__main__":
    main()