from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]

PROPOSAL_DIR = ROOT_DIR / "knowledge" / "proposals"
BP_DIR = ROOT_DIR / "knowledge" / "bp"

PROPOSAL_FILES = {
    "counters": PROPOSAL_DIR / "counters_candidates.json",
    "champion_strength": PROPOSAL_DIR / "champion_strength_candidates.json",
    "team_combo": PROPOSAL_DIR / "team_combo_candidates.json",
}

TARGET_FILES = {
    "counters": BP_DIR / "counters.json",
    "champion_strength": BP_DIR / "champion_strength.json",
    "team_combo": BP_DIR / "team_combos.json",
}

MERGE_STATE_PATH = PROPOSAL_DIR / "merge_state.json"


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 解析失败：{path}\n{e}") from e


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def backup_file(path: Path) -> None:
    if not path.exists():
        return

    backup_path = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup_path.write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8")
    print(f"[备份] {path.relative_to(ROOT_DIR)} -> {backup_path.name}")


def clean_str(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text in {"暂无", "None", "null", "未知", "未知英雄"}:
        return ""

    return text


def get_first(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and clean_str(value) != "":
            return value
    return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        parts = [x.strip() for x in value.replace("，", ",").split(",")]
        return [x for x in parts if x]

    return [value]


def unique_refs(refs: list[Any]) -> list[Any]:
    result = []
    seen = set()

    for ref in refs:
        key = json.dumps(ref, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)

    return result


def candidate_fingerprint(kind: str, item: dict[str, Any]) -> str:
    text = json.dumps(
        {
            "kind": kind,
            "item": item,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_merge_state() -> dict[str, Any]:
    state = load_json(MERGE_STATE_PATH, default={})

    if not isinstance(state, dict):
        state = {}

    state.setdefault("merged", {})
    return state


def save_merge_state(state: dict[str, Any]) -> None:
    save_json(MERGE_STATE_PATH, state)


def is_approved(item: dict[str, Any]) -> bool:
    return item.get("review_status", "pending") == "approved"


def get_source_refs(item: dict[str, Any]) -> list[Any]:
    refs = item.get("source_refs", [])
    if not isinstance(refs, list):
        refs = [refs]

    source_url = item.get("source_url") or item.get("url")
    source_title = item.get("source_title") or item.get("title")

    if source_url or source_title:
        refs.append(
            {
                "title": source_title,
                "url": source_url,
            }
        )

    return unique_refs(refs)


def merge_record(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    merged.update(new)

    old_refs = old.get("source_refs", [])
    new_refs = new.get("source_refs", [])

    if not isinstance(old_refs, list):
        old_refs = [old_refs]

    if not isinstance(new_refs, list):
        new_refs = [new_refs]

    merged["source_refs"] = unique_refs(old_refs + new_refs)

    return merged


def upsert_list(
    records: list[dict[str, Any]],
    new_record: dict[str, Any],
    key_fields: list[str],
) -> str:
    new_key = tuple(clean_str(new_record.get(field)) for field in key_fields)

    for index, old_record in enumerate(records):
        old_key = tuple(clean_str(old_record.get(field)) for field in key_fields)

        if old_key == new_key:
            records[index] = merge_record(old_record, new_record)
            return "updated"

    records.append(new_record)
    return "added"


def normalize_counter_candidate(item: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    """
    返回：
    side: good_against / bad_against
    record: counters.json 里的单条关系
    error: 如果无法识别，返回错误信息
    """

    source_champion = clean_str(
        get_first(
            item,
            [
                "champion",
                "source_champion",
                "from_champion",
                "subject_champion",
                "hero",
                "champion_id",
            ],
        )
    )

    target_champion = clean_str(
        get_first(
            item,
            [
                "target_champion",
                "enemy_champion",
                "opponent_champion",
                "against_champion",
                "target",
                "enemy",
                "opponent",
            ],
        )
    )

    counter_champion = clean_str(
        get_first(
            item,
            [
                "counter_champion",
                "counter",
                "countered_by",
                "counterpick",
            ],
        )
    )

    # 兼容这种结构：
    # target_champion = Azir
    # counter_champion = Talon
    # score = -4
    # 表示 Azir bad_against Talon
    if not source_champion and target_champion and counter_champion:
        source_champion = target_champion
        target_champion = counter_champion

    if source_champion and not target_champion and counter_champion:
        target_champion = counter_champion

    if not source_champion:
        return "", {}, "缺少 source champion"

    if not target_champion:
        return "", {}, "缺少 target champion"

    score = safe_int(item.get("score"), 0)

    relation = clean_str(
        get_first(
            item,
            [
                "relation",
                "direction",
                "type",
                "relation_type",
            ],
        )
    ).lower()

    if score < 0:
        side = "bad_against"
    elif score > 0:
        side = "good_against"
    else:
        if any(word in relation for word in ["bad", "weak", "countered_by", "被克制", "劣势"]):
            side = "bad_against"
        else:
            side = "good_against"

    # 如果 relation 明确写了 bad/good，则以 relation 辅助纠偏
    if any(word in relation for word in ["bad_against", "weak_against", "countered_by", "被克制", "劣势"]):
        side = "bad_against"
    elif any(word in relation for word in ["good_against", "strong_against", "counter_to", "克制", "优势"]):
        if score < 0:
            side = "bad_against"
        else:
            side = "good_against"

    record = {
        "champion": target_champion,
        "score": score,
        "role": clean_str(item.get("role") or item.get("lane")),
        "confidence": clean_str(item.get("confidence")) or "unknown",
        "source_type": clean_str(item.get("source_type")) or "unknown",
        "reason": clean_str(item.get("reason") or item.get("raw_evidence") or item.get("description")),
        "source_refs": get_source_refs(item),
        "merged_from": "proposals/counters_candidates.json",
        "merged_at": now_text(),
    }

    # 清掉空字段
    record = {k: v for k, v in record.items() if v not in ["", [], None]}

    return side, {"source_champion": source_champion, "record": record}, None


def normalize_strength_candidate(item: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    champion = clean_str(
        get_first(
            item,
            [
                "champion",
                "champion_id",
                "hero",
                "source_champion",
            ],
        )
    )

    if not champion:
        return {}, "缺少 champion"

    score = item.get("score", item.get("strength_score", item.get("tier_score", 0)))

    record = {
        "champion": champion,
        "role": clean_str(item.get("role") or item.get("lane")),
        "score": safe_int(score, 0),
        "strength_score": safe_int(score, 0),
        "score_type": clean_str(item.get("score_type") or item.get("type")),
        "tier": clean_str(item.get("tier")),
        "patch": clean_str(item.get("patch") or item.get("version")),
        "confidence": clean_str(item.get("confidence")) or "unknown",
        "source_type": clean_str(item.get("source_type")) or "unknown",
        "reason": clean_str(item.get("reason") or item.get("raw_evidence") or item.get("description")),
        "source_refs": get_source_refs(item),
        "merged_from": "proposals/champion_strength_candidates.json",
        "merged_at": now_text(),
    }

    record = {k: v for k, v in record.items() if v not in ["", [], None]}

    return record, None


def normalize_team_combo_candidate(item: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    champions = safe_list(item.get("champions"))

    if not champions:
        champion_a = clean_str(item.get("champion_a") or item.get("champion1"))
        champion_b = clean_str(item.get("champion_b") or item.get("champion2"))

        champions = [x for x in [champion_a, champion_b] if x]

    champions = [clean_str(x) for x in champions if clean_str(x)]

    if len(champions) < 2:
        return {}, "team_combo 至少需要 2 个英雄"

    roles = safe_list(item.get("roles"))
    roles = [clean_str(x) for x in roles if clean_str(x)]

    score = item.get("score", item.get("combo_score", 0))

    record = {
        "id": clean_str(item.get("id")),
        "champions": champions,
        "roles": roles,
        "combo_type": clean_str(item.get("combo_type") or item.get("type")),
        "score": safe_int(score, 0),
        "confidence": clean_str(item.get("confidence")) or "unknown",
        "source_type": clean_str(item.get("source_type")) or "unknown",
        "reason": clean_str(item.get("reason") or item.get("raw_evidence") or item.get("description")),
        "source_refs": get_source_refs(item),
        "merged_from": "proposals/team_combo_candidates.json",
        "merged_at": now_text(),
    }

    if not record["id"]:
        combo_key = "_".join(sorted(champions))
        combo_type = record.get("combo_type", "combo") or "combo"
        record["id"] = f"{combo_type}_{combo_key}"

    record = {k: v for k, v in record.items() if v not in ["", [], None]}

    return record, None


def load_proposals(kind: str) -> list[dict[str, Any]]:
    path = PROPOSAL_FILES[kind]
    data = load_json(path, default=[])

    if not isinstance(data, list):
        raise RuntimeError(f"{path} 必须是 JSON 数组")

    return [x for x in data if isinstance(x, dict)]


def load_target(kind: str) -> Any:
    path = TARGET_FILES[kind]

    if kind == "counters":
        data = load_json(path, default={})
        return data if isinstance(data, dict) else {}

    data = load_json(path, default=[])
    return data if isinstance(data, list) else []


def merge_counters(
    proposals: list[dict[str, Any]],
    target: dict[str, Any],
    state: dict[str, Any],
    include_merged: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "approved": 0,
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "already_merged": 0,
        "errors": 0,
    }

    for item in proposals:
        if not is_approved(item):
            continue

        stats["approved"] += 1

        fingerprint = candidate_fingerprint("counters", item)

        if fingerprint in state["merged"] and not include_merged:
            stats["already_merged"] += 1
            continue

        side, payload, error = normalize_counter_candidate(item)

        if error:
            stats["errors"] += 1
            print(f"[跳过 counters] {error}: {item}")
            continue

        source_champion = payload["source_champion"]
        record = payload["record"]

        if source_champion not in target or not isinstance(target.get(source_champion), dict):
            target[source_champion] = {}

        target[source_champion].setdefault("good_against", [])
        target[source_champion].setdefault("bad_against", [])

        action = upsert_list(
            records=target[source_champion][side],
            new_record=record,
            key_fields=["champion", "role"],
        )

        stats[action] += 1

        if not dry_run:
            state["merged"][fingerprint] = {
                "kind": "counters",
                "merged_at": now_text(),
                "target_file": str(TARGET_FILES["counters"].relative_to(ROOT_DIR)),
                "source_champion": source_champion,
                "side": side,
                "target_champion": record.get("champion"),
            }

    return stats


def merge_strength(
    proposals: list[dict[str, Any]],
    target: list[dict[str, Any]],
    state: dict[str, Any],
    include_merged: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "approved": 0,
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "already_merged": 0,
        "errors": 0,
    }

    for item in proposals:
        if not is_approved(item):
            continue

        stats["approved"] += 1

        fingerprint = candidate_fingerprint("champion_strength", item)

        if fingerprint in state["merged"] and not include_merged:
            stats["already_merged"] += 1
            continue

        record, error = normalize_strength_candidate(item)

        if error:
            stats["errors"] += 1
            print(f"[跳过 champion_strength] {error}: {item}")
            continue

        action = upsert_list(
            records=target,
            new_record=record,
            key_fields=["champion", "role", "patch", "source_type"],
        )

        stats[action] += 1

        if not dry_run:
            state["merged"][fingerprint] = {
                "kind": "champion_strength",
                "merged_at": now_text(),
                "target_file": str(TARGET_FILES["champion_strength"].relative_to(ROOT_DIR)),
                "champion": record.get("champion"),
                "role": record.get("role"),
            }

    return stats


def merge_team_combo(
    proposals: list[dict[str, Any]],
    target: list[dict[str, Any]],
    state: dict[str, Any],
    include_merged: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "approved": 0,
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "already_merged": 0,
        "errors": 0,
    }

    for item in proposals:
        if not is_approved(item):
            continue

        stats["approved"] += 1

        fingerprint = candidate_fingerprint("team_combo", item)

        if fingerprint in state["merged"] and not include_merged:
            stats["already_merged"] += 1
            continue

        record, error = normalize_team_combo_candidate(item)

        if error:
            stats["errors"] += 1
            print(f"[跳过 team_combo] {error}: {item}")
            continue

        record["_merge_key"] = "|".join(sorted(record.get("champions", []))) + "|" + clean_str(record.get("combo_type"))

        action = upsert_list(
            records=target,
            new_record=record,
            key_fields=["_merge_key"],
        )

        for combo in target:
            combo.pop("_merge_key", None)

        stats[action] += 1

        if not dry_run:
            state["merged"][fingerprint] = {
                "kind": "team_combo",
                "merged_at": now_text(),
                "target_file": str(TARGET_FILES["team_combo"].relative_to(ROOT_DIR)),
                "champions": record.get("champions", []),
            }

    return stats


def print_stats(kind: str, stats: dict[str, int]) -> None:
    print(f"\n[{kind}]")
    print(f"approved:       {stats.get('approved', 0)}")
    print(f"added:          {stats.get('added', 0)}")
    print(f"updated:        {stats.get('updated', 0)}")
    print(f"already_merged: {stats.get('already_merged', 0)}")
    print(f"errors:         {stats.get('errors', 0)}")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--kind",
        choices=["all", "counters", "champion_strength", "team_combo"],
        default="all",
        help="要合并哪一类候选",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览，不写入正式知识库",
    )

    parser.add_argument(
        "--include-merged",
        action="store_true",
        help="包括已经合并过的候选。默认会根据 merge_state.json 跳过已合并项。",
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="写入前不备份旧文件",
    )

    args = parser.parse_args()

    kinds = ["counters", "champion_strength", "team_combo"] if args.kind == "all" else [args.kind]

    state = load_merge_state()

    changed_targets: dict[str, Any] = {}

    print(f"[ROOT] {ROOT_DIR}")
    print(f"[模式] {'dry-run' if args.dry_run else 'write'}")

    for kind in kinds:
        proposals = load_proposals(kind)
        target = load_target(kind)

        if kind == "counters":
            stats = merge_counters(
                proposals=proposals,
                target=target,
                state=state,
                include_merged=args.include_merged,
                dry_run=args.dry_run,
            )
        elif kind == "champion_strength":
            stats = merge_strength(
                proposals=proposals,
                target=target,
                state=state,
                include_merged=args.include_merged,
                dry_run=args.dry_run,
            )
        elif kind == "team_combo":
            stats = merge_team_combo(
                proposals=proposals,
                target=target,
                state=state,
                include_merged=args.include_merged,
                dry_run=args.dry_run,
            )
        else:
            raise RuntimeError(f"未知 kind: {kind}")

        print_stats(kind, stats)
        changed_targets[kind] = target

    if args.dry_run:
        print("\n[dry-run] 没有写入任何文件。")
        return

    for kind, target in changed_targets.items():
        target_path = TARGET_FILES[kind]

        if not args.no_backup:
            backup_file(target_path)

        save_json(target_path, target)
        print(f"[写入] {target_path.relative_to(ROOT_DIR)}")

    save_merge_state(state)
    print(f"[写入] {MERGE_STATE_PATH.relative_to(ROOT_DIR)}")

    print("\n[完成] approved candidates 已合并到 knowledge/bp。")


if __name__ == "__main__":
    main()