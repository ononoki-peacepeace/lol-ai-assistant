from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
GENERATE_SCRIPT = ROOT_DIR / "tools" / "knowledge" / "generate_proposal_from_sources.py"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_job(defaults: dict, job: dict) -> dict:
    merged = dict(defaults)
    merged.update(job)
    return merged


def make_job_key(job: dict) -> str:
    """
    用于判断任务是否重复。
    只看真正影响搜索结果的字段。
    """
    kind = job.get("kind", "auto")
    query = job.get("query", "")
    must_contain = job.get("must_contain", "")
    source_name = job.get("source_name", "")

    return f"{kind}||{query}||{must_contain}||{source_name}"


def build_command(job: dict, force_dry_run: bool = False) -> list[str]:
    kind = job.get("kind", "auto")
    query = job.get("query")
    source_name = job.get("source_name")
    must_contain = job.get("must_contain")

    max_results_per_source = int(job.get("max_results_per_source", 3))
    max_chars_per_result = int(job.get("max_chars_per_result", 20000))

    save_raw = bool(job.get("save_raw", False))
    dry_run = bool(job.get("dry_run", False)) or force_dry_run

    if not query:
        raise ValueError("job 缺少 query")

    cmd = [
        sys.executable,
        str(GENERATE_SCRIPT),
        "--kind",
        kind,
        "--query",
        query,
        "--max-results-per-source",
        str(max_results_per_source),
        "--max-chars-per-result",
        str(max_chars_per_result),
    ]

    if source_name:
        cmd.extend(["--source-name", source_name])

    if must_contain:
        cmd.extend(["--must-contain", must_contain])

    if dry_run:
        cmd.append("--dry-run")

    if save_raw:
        cmd.append("--save-raw")

    return cmd


def mark_job_done(config: dict, job_index: int, job: dict, config_path: Path):
    """
    成功后：
    1. 从 jobs 移除
    2. 加入 completed_jobs
    3. 立刻写回文件，防止中途断了丢进度
    """
    jobs = config.get("jobs", [])
    completed_jobs = config.setdefault("completed_jobs", [])

    done_job = dict(job)
    done_job["status"] = "done"
    done_job["completed_at"] = datetime.now().isoformat(timespec="seconds")

    completed_jobs.append(done_job)

    # 注意：这里按 index 删除原始 job
    if 0 <= job_index < len(jobs):
        jobs.pop(job_index)

    write_json(config_path, config)


def mark_job_failed(config: dict, job_index: int, job: dict, config_path: Path, error: str = ""):
    """
    失败不从 jobs 移除，只记录失败次数。
    以后还能重试。
    """
    jobs = config.get("jobs", [])

    if 0 <= job_index < len(jobs):
        current = jobs[job_index]
        current["last_status"] = "failed"
        current["failed_count"] = int(current.get("failed_count", 0)) + 1
        current["last_failed_at"] = datetime.now().isoformat(timespec="seconds")

        if error:
            current["last_error"] = error[:500]

    write_json(config_path, config)


def remove_completed_duplicates(config: dict):
    """
    如果 jobs 里还有和 completed_jobs 重复的任务，启动时自动清掉。
    """
    jobs = config.get("jobs", [])
    completed_jobs = config.get("completed_jobs", [])

    completed_keys = {
        make_job_key(job)
        for job in completed_jobs
        if isinstance(job, dict)
    }

    new_jobs = []

    removed_count = 0

    for job in jobs:
        key = make_job_key(job)

        if key in completed_keys:
            removed_count += 1
            continue

        new_jobs.append(job)

    config["jobs"] = new_jobs

    return removed_count


def run_jobs_once(args) -> int:
    config_path = Path(args.config)

    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path

    config = load_json(config_path)

    config.setdefault("defaults", {})
    config.setdefault("jobs", [])
    config.setdefault("completed_jobs", [])
    config.setdefault("failed_jobs", [])

    if not args.dry_run and not args.no_update:
        removed_count = remove_completed_duplicates(config)
        if removed_count:
            print(f"[去重] 已移除 jobs 中重复的 completed 任务：{removed_count} 条")
            write_json(config_path, config)

    defaults = config.get("defaults", {})
    jobs = config.get("jobs", [])

    if not isinstance(jobs, list):
        raise ValueError("config.jobs 必须是数组")

    print(f"[配置] {config_path}")
    print(f"[待执行任务数] {len(jobs)}")
    print(f"[已完成任务数] {len(config.get('completed_jobs', []))}")

    if not jobs:
        return 0

    executed = 0
    success = 0
    failed = 0

    index = 0

    while index < len(config.get("jobs", [])):
        if args.limit > 0 and executed >= args.limit:
            break

        raw_job = config["jobs"][index]
        job = merge_job(defaults, raw_job)
        name = job.get("name", f"job-{index}")

        print("\n" + "=" * 80)
        print(f"[任务] index={index} name={name}")
        print(f"[kind] {job.get('kind')}")
        print(f"[query] {job.get('query')}")
        print(f"[source] {job.get('source_name')}")
        print(f"[must_contain] {job.get('must_contain')}")

        try:
            cmd = build_command(job, force_dry_run=args.dry_run)
        except Exception as e:
            print(f"[失败] 构造命令失败：{e}")
            failed += 1
            executed += 1
            index += 1
            continue

        print("[执行]")
        print(" ".join(f'"{x}"' if " " in x else x for x in cmd))

        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        executed += 1

        if result.returncode == 0:
            success += 1
            print("[成功]")

            if not args.dry_run and not args.no_update:
                mark_job_done(
                    config=config,
                    job_index=index,
                    job=raw_job,
                    config_path=config_path,
                )
                # 成功后当前 job 已经 pop 掉，所以不要 index += 1
                continue

        else:
            failed += 1
            print(f"[失败] returncode={result.returncode}")

            if not args.dry_run and not args.no_update:
                mark_job_failed(
                    config=config,
                    job_index=index,
                    job=raw_job,
                    config_path=config_path,
                    error=f"returncode={result.returncode}",
                )

        index += 1

        if args.sleep > 0:
            time.sleep(args.sleep)

    print("\n" + "=" * 80)
    print("[本轮完成]")
    print(f"执行任务数：{executed}")
    print(f"成功任务数：{success}")
    print(f"失败任务数：{failed}")
    print(f"剩余待执行任务数：{len(config.get('jobs', []))}")
    print(f"累计完成任务数：{len(config.get('completed_jobs', []))}")

    return executed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        required=True,
        help="搜索任务 JSON，例如 knowledge/search/bp_search_jobs.json",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="强制所有任务 dry-run，不写入 proposals，也不移动到 completed_jobs",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="每轮最多执行多少个任务，0 表示不限制",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="每个任务之间等待秒数",
    )

    parser.add_argument(
        "--no-update",
        action="store_true",
        help="不更新 config 文件。调试用。",
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help="持续监听任务文件，有任务就执行，没有任务就等待。",
    )

    parser.add_argument(
        "--idle-sleep",
        type=float,
        default=10.0,
        help="loop 模式下没有任务时等待秒数。",
    )

    args = parser.parse_args()

    while True:
        executed = run_jobs_once(args)

        if not args.loop:
            break

        if executed == 0:
            print(f"[LOOP] 暂无任务，{args.idle_sleep} 秒后继续检查。")
            time.sleep(args.idle_sleep)
        else:
            print("[LOOP] 本轮有任务执行，继续检查队列。")

if __name__ == "__main__":
    main()