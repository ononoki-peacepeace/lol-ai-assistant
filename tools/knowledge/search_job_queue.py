from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_PATH = ROOT_DIR / "knowledge" / "search" / "bp_search_jobs.json"


DEFAULT_DATA = {
    "defaults": {
        "max_results_per_source": 1,
        "max_chars_per_result": 4000,
        "save_raw": True
    },
    "jobs": [],
    "completed_jobs": [],
    "failed_jobs": []
}


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_queue(path: Path = DEFAULT_QUEUE_PATH) -> dict[str, Any]:
    if not path.exists():
        save_queue(DEFAULT_DATA, path)
        return json.loads(json.dumps(DEFAULT_DATA, ensure_ascii=False))

    text = path.read_text(encoding="utf-8-sig").strip()

    if not text:
        return json.loads(json.dumps(DEFAULT_DATA, ensure_ascii=False))

    data = json.loads(text)

    data.setdefault("defaults", DEFAULT_DATA["defaults"])
    data.setdefault("jobs", [])
    data.setdefault("completed_jobs", [])
    data.setdefault("failed_jobs", [])

    return data


def save_queue(data: dict[str, Any], path: Path = DEFAULT_QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(path.suffix + ".tmp")

    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    temp_path.replace(path)


def clean(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text in {"", "暂无", "None", "null", "未知", "未知英雄"}:
        return ""

    return text


def make_job_key(job: dict[str, Any]) -> str:
    kind = clean(job.get("kind", "auto"))
    query = clean(job.get("query"))
    must_contain = clean(job.get("must_contain"))
    source_name = clean(job.get("source_name"))

    return f"{kind}||{query}||{must_contain}||{source_name}"


def get_all_job_keys(data: dict[str, Any]) -> set[str]:
    keys = set()

    for group in ["jobs", "completed_jobs", "failed_jobs"]:
        for job in data.get(group, []):
            if isinstance(job, dict):
                keys.add(make_job_key(job))

    return keys


def append_jobs(
    jobs: list[dict[str, Any]],
    queue_path: Path = DEFAULT_QUEUE_PATH,
    match_id: str | None = None,
) -> int:
    data = load_queue(queue_path)
    existing_keys = get_all_job_keys(data)

    added = 0

    for job in jobs:
        if not isinstance(job, dict):
            continue

        if not clean(job.get("query")):
            continue

        normalized = dict(job)
        normalized.setdefault("kind", "auto")
        normalized.setdefault("created_at", now_text())

        if match_id:
            normalized.setdefault("match_id", match_id)

        job_key = make_job_key(normalized)

        if job_key in existing_keys:
            continue

        normalized["job_key"] = job_key

        data["jobs"].append(normalized)
        existing_keys.add(job_key)
        added += 1

    save_queue(data, queue_path)

    return added
def get_rec_champion(item: dict[str, Any]) -> str:
    return clean(
        item.get("champion")
        or item.get("champion_id")
        or item.get("id")
        or item.get("name")
        or item.get("display_name")
    )

def build_jobs_from_bp(
    recommendations: list[dict[str, Any]],
    ally_picks: list[str],
    enemy_picks: list[str],
    target_role: str | None = None,
    lane_opponent: str | None = None,
    lane_opponents: list[str] | None = None,
    max_jobs: int = 4,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []

    ally = [clean(x) for x in ally_picks if clean(x)]
    enemy = [clean(x) for x in enemy_picks if clean(x)]

    candidates = [
        get_rec_champion(item)
        for item in recommendations[:5]
        if isinstance(item, dict) and get_rec_champion(item)
    ]

    possible_lane_opponents = []

    if lane_opponent:
        possible_lane_opponents.append(clean(lane_opponent))

    for x in lane_opponents or []:
        x = clean(x)
        if x and x not in possible_lane_opponents:
            possible_lane_opponents.append(x)

    possible_lane_opponents = [
        x for x in possible_lane_opponents
        if x and x in enemy
    ]

    role_text = clean(target_role) or "lane"
    primary_candidate = candidates[0] if candidates else ""
    primary_opponent = possible_lane_opponents[0] if possible_lane_opponents else (enemy[0] if enemy else "")

    # 注意：
    # 如果你的 generate_proposal_from_sources.py 里 --kind 叫 "champion_strength"，
    # 就把下面的 "strength" 改成 "champion_strength"。
    strength_kind = "strength"

    # 1. 查：谁 counter 对线敌人
    if primary_opponent:
        jobs.append(
            {
                "name": f"Who counters {primary_opponent} {role_text}",
                "kind": "counters",
                "query": f"best counters to {primary_opponent} {role_text} current patch League of Legends win rate",
                "must_contain": primary_opponent,
                "source_name": "U.GG",
            }
        )

    # 2. 查：第一推荐英雄当前版本强度
    if primary_candidate:
        jobs.append(
            {
                "name": f"{primary_candidate} {role_text} current patch strength",
                "kind": strength_kind,
                "query": f"{primary_candidate} {role_text} tier win rate pick rate ban rate current patch League of Legends",
                "must_contain": primary_candidate,
                "source_name": "U.GG",
            }
        )

    # 3. 查：第一推荐英雄和我方队友配合
    if primary_candidate and ally:
        allies_for_query = ally[:3]
        allies_text = " ".join(allies_for_query)

        jobs.append(
            {
                "name": f"{primary_candidate} synergy with allies",
                "kind": "team_combo",
                "query": f"{primary_candidate} {allies_text} team comp synergy League of Legends",
                "must_contain": f"{primary_candidate}," + ",".join(allies_for_query),
                "source_name": "Reddit SummonerSchool",
            }
        )

    # 4. 查：对线敌人当前版本强度
    if primary_opponent:
        jobs.append(
            {
                "name": f"{primary_opponent} {role_text} current patch strength",
                "kind": strength_kind,
                "query": f"{primary_opponent} {role_text} tier win rate pick rate ban rate current patch League of Legends",
                "must_contain": primary_opponent,
                "source_name": "U.GG",
            }
        )

    # 5. 如果还有名额，查第二推荐英雄强度
    if len(candidates) >= 2:
        second_candidate = candidates[1]

        jobs.append(
            {
                "name": f"{second_candidate} {role_text} current patch strength",
                "kind": strength_kind,
                "query": f"{second_candidate} {role_text} tier win rate pick rate ban rate current patch League of Legends",
                "must_contain": second_candidate,
                "source_name": "U.GG",
            }
        )

    return jobs[:max_jobs]