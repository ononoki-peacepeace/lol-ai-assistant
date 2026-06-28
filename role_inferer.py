from __future__ import annotations

from itertools import count
from typing import Any

from config import CHAMPION_TAGS_PATH, load_json


ROLES = ["上单", "打野", "中单", "下路", "辅助"]


ROLE_ALIASES = {
    "top": "上单",
    "toplane": "上单",
    "top_lane": "上单",
    "上单": "上单",

    "jungle": "打野",
    "jungler": "打野",
    "jg": "打野",
    "打野": "打野",

    "mid": "中单",
    "middle": "中单",
    "midlane": "中单",
    "mid_lane": "中单",
    "中单": "中单",

    "adc": "下路",
    "bot": "下路",
    "bottom": "下路",
    "marksman": "下路",
    "射手": "下路",
    "下路": "下路",

    "support": "辅助",
    "sup": "辅助",
    "辅助": "辅助",
}


def clean_champion_id(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text in {"", "暂无", "None", "null", "未知", "未知英雄"}:
        return ""

    return text


def normalize_role(role: Any) -> str | None:
    if role is None:
        return None

    text = str(role).strip()
    lower = text.lower()

    return ROLE_ALIASES.get(lower) or ROLE_ALIASES.get(text) or None


def safe_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [x.strip() for x in value.replace("，", ",").split(",") if x.strip()]

    return [value]


class RoleInferer:
    def __init__(self):
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})

    def get_role_options(self, champion_id: str) -> list[dict[str, Any]]:
        """
        返回这个英雄可能的位置。

        格式：
        [
          {"role": "上单", "score": 4, "source": "main_role"},
          {"role": "中单", "score": 3, "source": "roles"}
        ]

        score 越高，越像主要位置。
        """
        champion_id = clean_champion_id(champion_id)

        if not champion_id:
            return []

        raw = self.champion_tags.get(champion_id, None)

        options: dict[str, dict[str, Any]] = {}

        def add_role(role_value: Any, score: int, source: str):
            role = normalize_role(role_value)

            if not role:
                return

            old = options.get(role)

            if old is None or score > old["score"]:
                options[role] = {
                    "role": role,
                    "score": score,
                    "source": source,
                }

        if isinstance(raw, dict):
            # 主位置字段，权重最高
            for key in [
                "main_role",
                "primary_role",
                "main_lane",
                "primary_lane",
                "role",
                "position",
            ]:
                value = raw.get(key)

                for part in safe_list(value):
                    add_role(part, 4, key)

            # 多位置字段
            for key in [
                "roles",
                "lanes",
                "positions",
                "possible_roles",
                "possible_lanes",
                "secondary_roles",
            ]:
                value = raw.get(key)

                for part in safe_list(value):
                    add_role(part, 3, key)

            # 普通 tags 里也可能写了 上单/中单/打野
            for part in safe_list(raw.get("tags")):
                add_role(part, 2, "tags")

        elif isinstance(raw, list):
            for part in raw:
                add_role(part, 2, "list_tags")

        elif isinstance(raw, str):
            add_role(raw, 2, "string_tag")

        result = list(options.values())

        # 如果完全没有位置信息，不要直接 unknown。
        # 给所有位置一个低分，让阵容分配还能继续跑。
        if not result:
            result = [
                {
                    "role": role,
                    "score": 0,
                    "source": "fallback_unknown",
                }
                for role in ROLES
            ]

        result.sort(key=lambda x: x["score"], reverse=True)

        return result

    def get_roles(self, champion_id: str) -> list[str]:
        return [x["role"] for x in self.get_role_options(champion_id)]

    def infer_team_roles(
        self,
        picks: list[str],
        max_results: int = 8,
    ) -> dict[str, Any]:
        """
        根据整个敌方阵容推断位置。

        返回：
        {
          "assignments": [
            {
              "roles": {"上单": "Aatrox", "打野": "LeeSin", ...},
              "champions": {"Aatrox": "上单", "LeeSin": "打野", ...},
              "score": 17
            }
          ]
        }
        """
        clean_picks = [
            clean_champion_id(x)
            for x in picks
            if clean_champion_id(x)
        ]

        clean_picks = clean_picks[:5]

        if not clean_picks:
            return {
                "picks": [],
                "assignments": [],
            }

        options_by_champion = {
            champion: self.get_role_options(champion)
            for champion in clean_picks
        }

        assignments = []

        def backtrack(
            index: int,
            used_roles: set[str],
            role_to_champion: dict[str, str],
            champion_to_role: dict[str, str],
            score: int,
            details: list[dict[str, Any]],
        ):
            if index >= len(clean_picks):
                assignments.append(
                    {
                        "roles": dict(role_to_champion),
                        "champions": dict(champion_to_role),
                        "score": score,
                        "details": list(details),
                    }
                )
                return

            champion = clean_picks[index]
            options = options_by_champion.get(champion, [])

            for option in options:
                role = option["role"]

                if role in used_roles:
                    continue

                used_roles.add(role)
                role_to_champion[role] = champion
                champion_to_role[champion] = role

                details.append(
                    {
                        "champion": champion,
                        "role": role,
                        "score": option["score"],
                        "source": option.get("source", ""),
                    }
                )

                backtrack(
                    index=index + 1,
                    used_roles=used_roles,
                    role_to_champion=role_to_champion,
                    champion_to_role=champion_to_role,
                    score=score + int(option["score"]),
                    details=details,
                )

                details.pop()
                champion_to_role.pop(champion, None)
                role_to_champion.pop(role, None)
                used_roles.remove(role)

        backtrack(
            index=0,
            used_roles=set(),
            role_to_champion={},
            champion_to_role={},
            score=0,
            details=[],
        )

        assignments.sort(key=lambda x: x["score"], reverse=True)

        return {
            "picks": clean_picks,
            "assignments": assignments[:max_results],
        }

    def get_lane_opponent_options(
        self,
        enemy_picks: list[str],
        target_role: str | None,
        max_results: int = 8,
    ) -> dict[str, Any]:
        target_role = normalize_role(target_role)

        if not target_role:
            return {
                "primary": "",
                "confidence": "unknown",
                "options": [],
                "assignments": [],
            }

        inferred = self.infer_team_roles(
            picks=enemy_picks,
            max_results=max_results,
        )

        assignments = inferred.get("assignments", [])

        if not assignments:
            return {
                "primary": "",
                "confidence": "unknown",
                "options": [],
                "assignments": [],
            }

        top_score = assignments[0]["score"]

        # 只看接近最优的几个阵容分配。
        # 比如最高 16 分，15/16 都算合理，10 分就不算了。
        near_best = [
            item
            for item in assignments
            if item["score"] >= top_score - 1
        ]

        if not near_best:
            near_best = assignments[:1]

        counts: dict[str, int] = {}
        best_score_by_champion: dict[str, int] = {}

        for assignment in near_best:
            champion = assignment.get("roles", {}).get(target_role)

            if not champion:
                continue

            counts[champion] = counts.get(champion, 0) + 1
            best_score_by_champion[champion] = max(
                best_score_by_champion.get(champion, -999),
                assignment.get("score", 0),
            )

        if not counts:
            return {
                "primary": "",
                "confidence": "unknown",
                "options": [],
                "assignments": assignments,
            }

        options = []

        total = sum(counts.values())

        for champion, c in counts.items():
            options.append(
                {
                    "champion": champion,
                    "count": c,
                    "ratio": c / total if total else 0,
                    "best_assignment_score": best_score_by_champion.get(champion, 0),
                }
            )

        options.sort(
            key=lambda x: (x["count"], x["best_assignment_score"]),
            reverse=True,
        )

        primary = options[0]["champion"]

        if len(options) == 1:
            confidence = "high"
        else:
            if options[0]["count"] > options[1]["count"]:
                confidence = "medium"
            else:
                confidence = "ambiguous"

        return {
            "primary": primary,
            "confidence": confidence,
            "options": options,
            "assignments": assignments,
        }

    def get_lane_opponent(
        self,
        enemy_picks: list[str],
        target_role: str | None,
    ) -> tuple[str, str]:
        """
        兼容旧代码。
        只返回 primary 和 confidence。
        """
        result = self.get_lane_opponent_options(
            enemy_picks=enemy_picks,
            target_role=target_role,
        )

        return result.get("primary", ""), result.get("confidence", "unknown")