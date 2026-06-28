import argparse
import json
import os
import re
from pathlib import Path

from tavily import TavilyClient

from generate_proposal_from_text import (
    KIND_CONFIG,
    generate_for_kind,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_PATH = PROJECT_ROOT / "knowledge" / "sources" / "knowledge_sources.json"


def load_json(path: Path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_tavily_client():
    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("环境变量 TAVILY_API_KEY 没有设置。")

    return TavilyClient(api_key=api_key)


def load_sources():
    data = load_json(SOURCES_PATH, default={})
    sources = data.get("sources", [])

    enabled_sources = []

    for source in sources:
        if not source.get("enabled", True):
            continue

        if not source.get("domain"):
            continue

        enabled_sources.append(source)

    return enabled_sources


def build_source_query(base_query: str, source: dict) -> str:
    domain = source.get("domain", "")
    extra_keywords = source.get("extra_keywords", [])

    parts = [base_query]

    for keyword in extra_keywords:
        parts.append(str(keyword))

    if domain:
        parts.append(f"site:{domain}")

    return " ".join(parts)


def search_one_source(client: TavilyClient, query: str, source: dict, max_results: int):
    source_query = build_source_query(query, source)

    print("\n" + "=" * 70)
    print(f"[搜索来源] {source.get('name')} ({source.get('domain')})")
    print(f"[搜索语句] {source_query}")

    response = client.search(
        query=source_query,
        search_depth="advanced",
        max_results=max_results,
        include_raw_content=True,
        include_answer=False,
    )

    return response.get("results", [])


def clean_web_content(content: str) -> str:
    """
    清理 Tavily 抽出来的网页正文：
    - 删除 markdown 图片
    - 删除图片链接
    - 删除过短/纯导航行
    """
    if not content:
        return ""

    # 删除 markdown 图片：![xxx](url)
    content = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", content)

    # 普通 markdown 链接保留文字：[文字](url) -> 文字
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

    lines = []

    for line in content.splitlines():
        line = line.strip()

        if not line:
            continue

        lower = line.lower()

        # 跳过图片/CDN/icon 垃圾
        if "image=q_auto" in lower:
            continue
        if "s-opgg-kit.op.gg" in lower:
            continue
        if lower.startswith("http") and any(x in lower for x in [".svg", ".png", ".jpg", ".webp"]):
            continue

        # 跳过很短的导航碎片
        if len(line) <= 2:
            continue

        lines.append(line)

    return "\n".join(lines)

def build_focus_keywords(query: str, must_contain: str | None = None) -> list[str]:
    keywords = []

    # 从 query 里拆关键词
    for part in re.split(r"[\s,，]+", query):
        part = part.strip()
        if not part:
            continue

        # 英文太短的词跳过，但中文两个字也要保留，比如“诺手”
        if part.isascii() and len(part) < 3:
            continue

        keywords.append(part.lower())

    # 从 --must-contain 里补充关键词
    if must_contain:
        for part in re.split(r"[,，]+", must_contain):
            part = part.strip()
            if part:
                keywords.append(part.lower())

    # 通用 LOL 数据关键词
    generic_keywords = [
        "counter",
        "counters",
        "matchup",
        "matchups",
        "win rate",
        "pick rate",
        "ban rate",
        "matches",
        "tier",
        "top",
        "mid",
        "jungle",
        "bottom",
        "support",
        "lane",
        "胜率",
        "登场率",
        "禁用率",
        "克制",
        "对线",
        "难打",
        "好打",
        "强度",
        "上单",
        "打野",
        "中单",
        "下路",
        "辅助"
    ]

    keywords.extend(generic_keywords)

    # 去重，保持顺序
    seen = set()
    result = []

    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            result.append(keyword)

    return result

def prioritize_content(
    content: str,
    query: str,
    max_chars: int,
    must_contain: str | None = None,
) -> str:
    """
    如果正文太长，优先保留和查询主题、英雄名、LOL 数据相关的行。
    不写死任何英雄。
    """
    if not max_chars or len(content) <= max_chars:
        return content

    important_keywords = build_focus_keywords(
        query=query,
        must_contain=must_contain,
    )

    selected_lines = []

    for line in content.splitlines():
        lower = line.lower()

        if any(keyword in lower for keyword in important_keywords):
            selected_lines.append(line)

    selected_text = "\n".join(selected_lines).strip()

    # 如果关键词筛完太少，说明没筛到有效内容，退回清洗后的前 max_chars
    if len(selected_text) < 300:
        return content[:max_chars] + "\n...[内容过长，已截断]"

    if len(selected_text) > max_chars:
        selected_text = selected_text[:max_chars] + "\n...[相关内容过长，已截断]"

    return selected_text

def result_to_text(
    result: dict,
    source: dict,
    max_chars_per_result: int,
    query: str,
    must_contain: str | None = None,
) -> str:
    title = result.get("title", "")
    url = result.get("url", "")
    content = result.get("raw_content") or result.get("content") or ""

    content = clean_web_content(content)
    content = prioritize_content(
        content=content,
        query=query,
        max_chars=max_chars_per_result,
        must_contain=must_contain,
    )

    return f"""
    查询主题：{query}

    来源名称：{source.get("name", "")}
    来源类型：{source.get("type", "")}
    来源域名：{source.get("domain", "")}
    网页标题：{title}
    网页URL：{url}

    正文：
    {content}
    """.strip()

def save_raw_snapshot(text: str, query: str, source: dict, index: int):
    raw_dir = PROJECT_ROOT / "knowledge" / "raw" / "web_snapshots"
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_name = source.get("name", "source")
    safe = f"{query}_{source_name}_{index}"
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in safe)
    safe = safe[:120]

    path = raw_dir / f"{safe}.txt"
    path.write_text(text, encoding="utf-8")

    print(f"[保存快照] {path.relative_to(PROJECT_ROOT)}")


def run_ai_extract(kind: str, source_text: str, dry_run: bool):
    if kind == "auto":
        total_added = 0
        all_ok = True

        for real_kind in KIND_CONFIG.keys():
            added, ok = generate_for_kind(
                kind=real_kind,
                source_text=source_text,
                dry_run=dry_run,
            )
            total_added += added

            if not ok:
                all_ok = False

        return total_added, all_ok

    added, ok = generate_for_kind(
        kind=kind,
        source_text=source_text,
        dry_run=dry_run,
    )

    return added, ok


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--kind",
        required=True,
        choices=["auto", *KIND_CONFIG.keys()],
        help="生成哪类候选：auto / counters / strength / team_combo"
    )

    parser.add_argument(
        "--must-contain",
        help="结果必须包含这些关键词之一，用逗号分隔，例如 Darius,诺手"
    )

    parser.add_argument(
        "--query",
        required=True,
        help="基础搜索关键词，例如：诺手 上单 对线 克制 难打"
    )

    parser.add_argument(
        "--max-results-per-source",
        type=int,
        default=2,
        help="每个来源最多取几个结果，默认 2"
    )

    parser.add_argument(
        "--max-chars-per-result",
        type=int,
        default=6000,
        help="每个网页最多喂给 AI 的字符数，默认 6000"
    )

    parser.add_argument(
        "--source-name",
        help="只搜索某一个来源名称，例如 LoLalytics"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 AI 结果，不写入 proposals"
    )

    parser.add_argument(
        "--save-raw",
        action="store_true",
        help="保存网页快照到 knowledge/raw/web_snapshots"
    )

    args = parser.parse_args()

    sources = load_sources()

    if args.source_name:
        sources = [
            s for s in sources
            if s.get("name", "").lower() == args.source_name.lower()
        ]

    if not sources:
        print("[结束] 没有可用 source。请检查 knowledge/sources/knowledge_sources.json")
        return

    client = get_tavily_client()
    total_added = 0
    total_pages = 0
    failed_count = 0

    for source in sources:
        try:
            results = search_one_source(
                client=client,
                query=args.query,
                source=source,
                max_results=args.max_results_per_source,
            )
        except Exception as e:
            print(f"[失败] 搜索来源失败：{source.get('name')}，错误：{e}")
            failed_count += 1
            continue

        if not results:
            print("[跳过] 没有搜索结果。")
            continue

        for index, result in enumerate(results, start=1):
            source_text = result_to_text(
                result=result,
                source=source,
                max_chars_per_result=args.max_chars_per_result,
                query=args.query,
                must_contain=args.must_contain,
            )

            if args.must_contain:
                keywords = [
                    x.strip().lower()
                    for x in args.must_contain.split(",")
                    if x.strip()
                ]
                haystack = source_text.lower()

                if keywords and not any(keyword in haystack for keyword in keywords):
                    print(f"[跳过] 网页不包含关键词：{args.must_contain}")
                    continue

            if not source_text.strip():
                continue

            total_pages += 1

            print("\n===== 网页文本预览 =====")
            print(source_text[:1200])

            if args.save_raw:
                save_raw_snapshot(
                    text=source_text,
                    query=args.query,
                    source=source,
                    index=index,
                )

            added, ok = run_ai_extract(
                kind=args.kind,
                source_text=source_text,
                dry_run=args.dry_run,
            )

            total_added += added

            if not ok:
                failed_count += 1

    print("\n" + "=" * 70)
    print("[完成]")
    print(f"处理网页数：{total_pages}")
    print(f"新增候选数：{total_added}")
    print(f"失败次数：{failed_count}")


if __name__ == "__main__":
    main()