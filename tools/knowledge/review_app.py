from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[2]
PROPOSAL_DIR = ROOT_DIR / "knowledge" / "proposals"

PROPOSAL_FILES = {
    "counters": PROPOSAL_DIR / "counters_candidates.json",
    "champion_strength": PROPOSAL_DIR / "champion_strength_candidates.json",
    "team_combo": PROPOSAL_DIR / "team_combo_candidates.json",
}


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]\n", encoding="utf-8")
        return []

    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    data = json.loads(text)

    if not isinstance(data, list):
        raise ValueError(f"{path} 必须是 JSON 数组")

    result = []
    for item in data:
        if isinstance(item, dict):
            item.setdefault("review_status", "pending")
            result.append(item)

    return result


def save_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def get_item_title(kind: str, item: dict[str, Any]) -> str:
    if kind == "counters":
        champion = item.get("champion") or item.get("source_champion") or "未知英雄"
        target = item.get("target") or item.get("target_champion") or item.get("enemy") or item.get("opponent") or ""
        relation = item.get("relation") or item.get("type") or ""
        return f"{champion} → {target} {relation}".strip()

    if kind == "champion_strength":
        champion = item.get("champion", "未知英雄")
        role = item.get("role", "")
        score = item.get("score", item.get("strength_score", ""))
        return f"{champion} {role} 强度 {score}".strip()

    if kind == "team_combo":
        champions = item.get("champions", [])
        if isinstance(champions, list):
            champions_text = " + ".join(champions)
        else:
            champions_text = str(champions)

        combo_type = item.get("combo_type", "")
        return f"{champions_text} {combo_type}".strip()

    return item.get("id", "未命名候选")


def render_basic_info(item: dict[str, Any]) -> None:
    cols = st.columns(4)

    with cols[0]:
        st.metric("score", item.get("score", item.get("strength_score", "无")))

    with cols[1]:
        st.metric("confidence", item.get("confidence", "unknown"))

    with cols[2]:
        st.metric("source_type", item.get("source_type", "unknown"))

    with cols[3]:
        st.metric("status", item.get("review_status", "pending"))


def update_status(
    kind: str,
    index: int,
    status: str,
    note: str | None = None,
) -> None:
    path = PROPOSAL_FILES[kind]
    data = load_json(path)

    if index < 0 or index >= len(data):
        st.error("索引不存在，可能文件已变化。")
        return

    data[index]["review_status"] = status

    if note:
        data[index]["review_note"] = note

    save_json(path, data)


def main() -> None:
    st.set_page_config(
        page_title="BP Knowledge Review",
        layout="wide",
    )

    st.title("LOL AI Assistant - Candidate Review")

    kind = st.sidebar.radio(
        "选择候选类型",
        list(PROPOSAL_FILES.keys()),
        format_func={
            "counters": "Counters 候选",
            "champion_strength": "Champion Strength 候选",
            "team_combo": "Team Combo 候选",
        }.get,
    )

    status_filter = st.sidebar.radio(
        "筛选状态",
        ["pending", "approved", "rejected", "all"],
        index=0,
    )

    path = PROPOSAL_FILES[kind]
    data = load_json(path)

    pending_count = sum(1 for x in data if x.get("review_status", "pending") == "pending")
    approved_count = sum(1 for x in data if x.get("review_status") == "approved")
    rejected_count = sum(1 for x in data if x.get("review_status") == "rejected")

    st.sidebar.markdown("---")
    st.sidebar.write(f"文件：`{path.relative_to(ROOT_DIR)}`")
    st.sidebar.write(f"总数：{len(data)}")
    st.sidebar.write(f"待审核：{pending_count}")
    st.sidebar.write(f"已通过：{approved_count}")
    st.sidebar.write(f"已拒绝：{rejected_count}")

    if st.sidebar.button("保存并刷新"):
        save_json(path, data)
        st.rerun()

    if not data:
        st.info("当前没有候选数据。")
        return

    visible_items = []

    for index, item in enumerate(data):
        status = item.get("review_status", "pending")

        if status_filter != "all" and status != status_filter:
            continue

        visible_items.append((index, item))

    st.subheader(f"{kind} / {status_filter} / {len(visible_items)} 条")

    if not visible_items:
        st.info("没有符合筛选条件的候选。")
        return

    for index, item in visible_items:
        title = get_item_title(kind, item)

        with st.expander(f"#{index}  {title}", expanded=False):
            render_basic_info(item)

            reason = item.get("reason") or item.get("raw_evidence") or item.get("description") or ""
            if reason:
                st.markdown("**Reason / Evidence**")
                st.write(reason)

            source_refs = item.get("source_refs", [])
            if source_refs:
                st.markdown("**Source refs**")
                st.json(source_refs, expanded=False)

            st.markdown("**完整 JSON**")
            st.json(item, expanded=False)

            note_key = f"note_{kind}_{index}"
            note = st.text_input(
                "审核备注，可选",
                key=note_key,
            )

            col1, col2, col3, col4 = st.columns([1, 1, 1, 5])

            with col1:
                if st.button("通过", key=f"approve_{kind}_{index}"):
                    update_status(kind, index, "approved", note)
                    st.success("已通过")
                    st.rerun()

            with col2:
                if st.button("拒绝", key=f"reject_{kind}_{index}"):
                    update_status(kind, index, "rejected", note)
                    st.warning("已拒绝")
                    st.rerun()

            with col3:
                if st.button("改回待审", key=f"pending_{kind}_{index}"):
                    update_status(kind, index, "pending", note)
                    st.info("已改回 pending")
                    st.rerun()


if __name__ == "__main__":
    main()