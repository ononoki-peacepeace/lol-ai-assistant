from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import (
    CHAMPIONS_PATH,
    CHAMPION_TAGS_PATH,
    COUNTERS_PATH,
    CHAMPION_STRENGTH_PATH,
    TEAM_COMBOS_PATH,
    load_json,
)


ROLE_ALIASES = {
    "top": "上单",
    "上单": "上单",

    "jungle": "打野",
    "jg": "打野",
    "打野": "打野",

    "mid": "中单",
    "middle": "中单",
    "中单": "中单",

    "adc": "下路",
    "bot": "下路",
    "bottom": "下路",
    "下路": "下路",
    "射手": "下路",

    "support": "辅助",
    "sup": "辅助",
    "辅助": "辅助",
}


ROLE_KEYWORDS = {
    "上单": {"上单", "top", "toplane", "top_lane"},
    "打野": {"打野", "jungle", "jg", "jungler"},
    "中单": {"中单", "mid", "middle", "midlane", "mid_lane"},
    "下路": {"下路", "adc", "bot", "bottom", "marksman", "射手"},
    "辅助": {"辅助", "support", "sup", "辅助位"},
}


def normalize_role(role: str | None) -> str | None:
    if not role:
        return None

    text = str(role).strip().lower()
    return ROLE_ALIASES.get(text, role)


def clean_champion_id(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text in {"", "暂无", "None", "null", "未知", "未知英雄"}:
        return ""

    return text


def confidence_multiplier(confidence: str | None) -> float:
    confidence = str(confidence or "").lower()

    if confidence == "high":
        return 1.2

    if confidence == "medium":
        return 1.0

    if confidence == "low":
        return 0.7

    return 0.8


def source_multiplier(source_type: str | None) -> float:
    source_type = str(source_type or "").lower()

    if source_type in {"manual_seed", "stats_site_manual"}:
        return 1.1

    if source_type in {"stats_site", "multi_source"}:
        return 1.0

    if source_type in {"synthetic_scenario_llm", "llm_generated"}:
        return 0.7

    return 0.9


def calc_weight(
    score: Any,
    confidence: str | None = "unknown",
    source_type: str | None = "",
    default: int = 3,
) -> int:
    try:
        base = abs(int(float(score)))
    except (TypeError, ValueError):
        base = default

    value = base
    value *= confidence_multiplier(confidence)
    value *= source_multiplier(source_type)

    return max(1, round(value))


class ChampionRecommender:
    def __init__(self, debug: bool | None = None):
        self.champions_raw = load_json(CHAMPIONS_PATH, default={})
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})

        self.counters = load_json(COUNTERS_PATH, default={})
        self.champion_strength = load_json(CHAMPION_STRENGTH_PATH, default=[])
        self.team_combos = load_json(TEAM_COMBOS_PATH, default=[])

        if debug is None:
            self.debug = os.environ.get("BP_SCORE_DEBUG", "0") == "1"
        else:
            self.debug = debug

        self.champions = self._normalize_champions(self.champions_raw)

    def _normalize_champions(self, data: Any) -> dict[str, dict[str, Any]]:
        """
        兼容几种 champions.json 格式：

        1. {
             "Aatrox": {"name": "暗裔剑魔", ...}
           }

        2. [
             {"id": "Aatrox", "name": "暗裔剑魔"}
           ]

        3. {
             "data": {
               "Aatrox": {"id": "Aatrox", "name": "Aatrox", "title": "..."}
             }
           }
        """
        result: dict[str, dict[str, Any]] = {}

        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]

        if isinstance(data, dict):
            for champion_id, info in data.items():
                champion_id = clean_champion_id(champion_id)

                if not champion_id:
                    continue

                if isinstance(info, dict):
                    item = dict(info)
                else:
                    item = {"name": str(info)}

                item.setdefault("id", champion_id)
                result[champion_id] = item

            return result

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue

                champion_id = clean_champion_id(
                    item.get("id")
                    or item.get("champion")
                    or item.get("champion_id")
                    or item.get("key")
                )

                if not champion_id:
                    continue

                result[champion_id] = dict(item)

            return result

        return result

    def get_display_name(self, champion_id: str) -> str:
        champion_id = clean_champion_id(champion_id)

        if not champion_id:
            return "未知英雄"

        info = self.champions.get(champion_id, {})

        if isinstance(info, dict):
            return (
                info.get("display_name")
                or info.get("cn_name")
                or info.get("name_cn")
                or info.get("name")
                or champion_id
            )

        return champion_id

    def get_tags(self, champion_id: str) -> list[str]:
        champion_id = clean_champion_id(champion_id)

        if not champion_id:
            return []

        raw = self.champion_tags.get(champion_id, [])

        if isinstance(raw, dict):
            tags = raw.get("tags", [])
            roles = raw.get("roles", [])
            lanes = raw.get("lanes", [])

            result = []

            if isinstance(tags, list):
                result.extend(tags)

            if isinstance(roles, list):
                result.extend(roles)

            if isinstance(lanes, list):
                result.extend(lanes)

            return [str(x) for x in result if x]

        if isinstance(raw, list):
            return [str(x) for x in raw if x]

        if isinstance(raw, str):
            return [raw]

        return []

    def champion_has_role(self, champion_id: str, target_role: str | None) -> bool:
        target_role = normalize_role(target_role)

        if not target_role:
            return True

        tags = self.get_tags(champion_id)
        tag_set = {str(tag).strip().lower() for tag in tags}

        role_keywords = ROLE_KEYWORDS.get(target_role, {target_role})

        for keyword in role_keywords:
            if str(keyword).lower() in tag_set:
                return True

        return False

    def get_candidate_ids(
        self,
        target_role: str | None = None,
        banned_champions: list[str] | None = None,
        ally_picks: list[str] | None = None,
        enemy_picks: list[str] | None = None,
    ) -> list[str]:
        banned_set = {
            clean_champion_id(x)
            for x in (banned_champions or [])
            if clean_champion_id(x)
        }

        picked_set = {
            clean_champion_id(x)
            for x in (ally_picks or []) + (enemy_picks or [])
            if clean_champion_id(x)
        }

        excluded = banned_set | picked_set

        candidates = []

        for champion_id in self.champions.keys():
            if champion_id in excluded:
                continue

            if not self.champion_has_role(champion_id, target_role):
                continue

            candidates.append(champion_id)

        return candidates

    def _extract_analysis_picks(self, analysis: dict[str, Any] | None) -> tuple[list[str], list[str], list[str]]:
        if not analysis:
            return [], [], []

        ally_picks = (
            analysis.get("ally_picks")
            or analysis.get("blue_picks")
            or []
        )

        enemy_picks = (
            analysis.get("enemy_picks")
            or analysis.get("red_picks")
            or []
        )

        banned_champions = (
            analysis.get("banned_champions")
            or analysis.get("bans")
            or analysis.get("blue_bans", []) + analysis.get("red_bans", [])
            or []
        )

        return ally_picks, enemy_picks, banned_champions

    def recommend(
        self,
        ally_picks: list[str] | None = None,
        enemy_picks: list[str] | None = None,
        banned_champions: list[str] | None = None,
        target_role: str | None = None,
        lane_opponent: str | None = None,
        lane_opponents: list[str] | None = None,
        top_n: int = 10,
        analysis: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        主推荐入口。

        支持两种调用方式：

        1. 新方式：
           recommend(
               ally_picks=[...],
               enemy_picks=[...],
               banned_champions=[...],
               target_role="上单",
               lane_opponent="Aatrox",
           )

        2. 兼容旧方式：
           recommend(
               analysis=analysis,
               target_role="上单",
           )
        """
        
        # 兼容旧 main.py 调用：
        # recommender.recommend(analysis, target_role=...)
        # 或 recommender.recommend(analysis, "上单")
        if isinstance(ally_picks, dict) and analysis is None:
            analysis = ally_picks
            ally_picks = None

        if isinstance(enemy_picks, str) and target_role is None:
            target_role = enemy_picks
            enemy_picks = None

        if kwargs.get("role") and target_role is None:
            target_role = kwargs.get("role")

        if kwargs.get("side"):
            # side 暂时不用，但吃掉这个参数，避免旧代码传进来影响
            pass

        if analysis is not None:
            a, e, b = self._extract_analysis_picks(analysis)

            if ally_picks is None:
                ally_picks = a

            if enemy_picks is None:
                enemy_picks = e

            if banned_champions is None:
                banned_champions = b

        ally_picks = [
            clean_champion_id(x)
            for x in (ally_picks or [])
            if clean_champion_id(x)
        ]

        enemy_picks = [
            clean_champion_id(x)
            for x in (enemy_picks or [])
            if clean_champion_id(x)
        ]

        banned_champions = [
            clean_champion_id(x)
            for x in (banned_champions or [])
            if clean_champion_id(x)
        ]

        target_role = normalize_role(target_role)
        lane_opponent = clean_champion_id(lane_opponent)
        lane_opponents = [
            clean_champion_id(x)
            for x in (lane_opponents or [])
            if clean_champion_id(x)
        ]

        if lane_opponent and lane_opponent not in lane_opponents:
            lane_opponents.insert(0, lane_opponent)
        candidate_ids = self.get_candidate_ids(
            target_role=target_role,
            banned_champions=banned_champions,
            ally_picks=ally_picks,
            enemy_picks=enemy_picks,
        )

        recommendations = []

        for champion_id in candidate_ids:
            total_score = 0
            reasons = []

            role_score, role_reasons = self._score_role_fit(
                candidate_id=champion_id,
                target_role=target_role,
            )

            tag_score, tag_reasons = self._score_tags(
                candidate_id=champion_id,
                ally_picks=ally_picks,
                enemy_picks=enemy_picks,
            )

            counter_score, counter_reasons = self._score_counters(
                candidate_id=champion_id,
                enemy_picks=enemy_picks,
                lane_opponent=lane_opponent,
            )

            team_combo_score, team_combo_reasons = self._score_team_combo(
                candidate_id=champion_id,
                ally_picks=ally_picks,
            )

            strength_score, strength_reasons = self._score_champion_strength(
                candidate_id=champion_id,
                target_role=target_role,
            )

            total_score += role_score
            total_score += tag_score
            total_score += counter_score
            total_score += team_combo_score
            total_score += strength_score

            reasons.extend(role_reasons)
            reasons.extend(tag_reasons)
            reasons.extend(counter_reasons)
            reasons.extend(team_combo_reasons)
            reasons.extend(strength_reasons)

            if self.debug:
                print(
                    f"[SCORE DEBUG] {champion_id} "
                    f"total={total_score} "
                    f"role={role_score} "
                    f"tag={tag_score} "
                    f"counter={counter_score} "
                    f"team_combo={team_combo_score} "
                    f"strength={strength_score}"
                )

            if total_score <= 0 and not reasons:
                continue

            display_name = self.get_display_name(champion_id)

            recommendations.append(
                {
                    # 新字段
                    "champion": champion_id,
                    "champion_id": champion_id,
                    "display_name": display_name,

                    # 兼容旧 print_recommendations / AICommentator
                    "id": champion_id,
                    "name": display_name,
                    "hero": display_name,

                    "score": total_score,
                    "role_score": role_score,
                    "tag_score": tag_score,
                    "counter_score": counter_score,
                    "team_combo_score": team_combo_score,
                    "strength_score": strength_score,

                    "reasons": reasons[:8],
                    "reason": "\n".join(reasons[:8]),
                    "description": "\n".join(reasons[:8]),
                }
            )

        recommendations.sort(
            key=lambda item: item.get("score", 0),
            reverse=True,
        )

        return recommendations[:top_n]

    def _score_role_fit(
        self,
        candidate_id: str,
        target_role: str | None,
    ) -> tuple[int, list[str]]:
        if not target_role:
            return 0, []

        if self.champion_has_role(candidate_id, target_role):
            return 3, [f"符合目标位置：{target_role} +3"]

        return -999, [f"不符合目标位置：{target_role}"]

    def _score_tags(
        self,
        candidate_id: str,
        ally_picks: list[str],
        enemy_picks: list[str],
    ) -> tuple[int, list[str]]:
        """
        简单本地标签加分。
        这里先不做太复杂，防止标签规则压过 JSON 证据。
        """
        tags = self.get_tags(candidate_id)
        tag_set = {str(x).lower() for x in tags}

        score = 0
        reasons = []

        if any(x in tag_set for x in ["开团", "engage", "强开"]):
            score += 1
            reasons.append("具备开团能力 +1")

        if any(x in tag_set for x in ["坦克", "tank", "前排"]):
            score += 1
            reasons.append("可以补充前排 +1")

        if any(x in tag_set for x in ["后期", "scaling", "carry"]):
            score += 1
            reasons.append("具备后期能力 +1")

        return score, reasons

    def _score_counters(
        self,
        candidate_id: str,
        enemy_picks: list[str],
        lane_opponent: str | None = None,
        lane_opponents: list[str] | None = None,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []
        used_relations = set()

        enemy_set = {
            clean_champion_id(champ)
            for champ in enemy_picks
            if clean_champion_id(champ)
        }

        if not enemy_set:
            return 0, []
        lane_opponent_set = {
            clean_champion_id(x)
            for x in (lane_opponents or [])
            if clean_champion_id(x)
        }

        if lane_opponent:
            lane_opponent_set.add(lane_opponent)

        def lane_bonus(enemy: str) -> int:
            if lane_opponent and enemy == lane_opponent:
                return 2
            if enemy in lane_opponent_set:
                return 1
            return 0
        candidate_info = self.counters.get(candidate_id, {})

        # 1. 候选英雄视角：
        # candidate.good_against enemy
        # candidate.bad_against enemy
        if isinstance(candidate_info, dict):
            for item in candidate_info.get("good_against", []):
                if not isinstance(item, dict):
                    continue

                enemy = clean_champion_id(item.get("champion"))

                if enemy not in enemy_set:
                    continue

                relation_key = ("candidate_good", candidate_id, enemy)

                if relation_key in used_relations:
                    continue

                used_relations.add(relation_key)

                weight = calc_weight(
                    item.get("score", 3),
                    confidence=item.get("confidence", "unknown"),
                    source_type=item.get("source_type", ""),
                    default=3,
                )

                weight += lane_bonus(enemy)

                score += weight

                reason = item.get("reason", "")
                reasons.append(
                    f"对 {self.get_display_name(enemy)} 有 counter 依据 +{weight}：{reason}"
                )

            for item in candidate_info.get("bad_against", []):
                if not isinstance(item, dict):
                    continue

                enemy = clean_champion_id(item.get("champion"))

                if enemy not in enemy_set:
                    continue

                relation_key = ("candidate_bad", candidate_id, enemy)

                if relation_key in used_relations:
                    continue

                used_relations.add(relation_key)

                weight = calc_weight(
                    item.get("score", -3),
                    confidence=item.get("confidence", "unknown"),
                    source_type=item.get("source_type", ""),
                    default=3,
                )

                weight += lane_bonus(enemy)

                score -= weight

                reason = item.get("reason", "")
                reasons.append(
                    f"面对 {self.get_display_name(enemy)} 有风险 -{weight}：{reason}"
                )

        # 2. 敌方英雄视角：
        # enemy.bad_against candidate -> candidate 加分
        # enemy.good_against candidate -> candidate 扣分
        for enemy in enemy_set:
            enemy_info = self.counters.get(enemy, {})

            if not isinstance(enemy_info, dict):
                continue

            for item in enemy_info.get("bad_against", []):
                if not isinstance(item, dict):
                    continue

                target = clean_champion_id(item.get("champion"))

                if target != candidate_id:
                    continue

                relation_key = ("enemy_bad", enemy, candidate_id)

                if relation_key in used_relations:
                    continue

                used_relations.add(relation_key)

                weight = calc_weight(
                    item.get("score", -3),
                    confidence=item.get("confidence", "unknown"),
                    source_type=item.get("source_type", ""),
                    default=3,
                )

                weight += lane_bonus(enemy)

                score += weight

                reason = item.get("reason", "")
                reasons.append(
                    f"{self.get_display_name(enemy)} 记录显示怕 {self.get_display_name(candidate_id)} +{weight}：{reason}"
                )

            for item in enemy_info.get("good_against", []):
                if not isinstance(item, dict):
                    continue

                target = clean_champion_id(item.get("champion"))

                if target != candidate_id:
                    continue

                relation_key = ("enemy_good", enemy, candidate_id)

                if relation_key in used_relations:
                    continue

                used_relations.add(relation_key)

                weight = calc_weight(
                    item.get("score", 3),
                    confidence=item.get("confidence", "unknown"),
                    source_type=item.get("source_type", ""),
                    default=3,
                )

                weight += lane_bonus(enemy)

                score -= weight

                reason = item.get("reason", "")
                reasons.append(
                    f"{self.get_display_name(enemy)} 对 {self.get_display_name(candidate_id)} 有优势 -{weight}：{reason}"
                )

        return score, reasons

    def _score_team_combo(
        self,
        candidate_id: str,
        ally_picks: list[str],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        ally_set = {
            clean_champion_id(champ)
            for champ in ally_picks
            if clean_champion_id(champ)
        }

        if not ally_set:
            return 0, []

        combos = self.team_combos

        if isinstance(combos, dict):
            if isinstance(combos.get("combos"), list):
                combos = combos["combos"]
            else:
                expanded = []

                for value in combos.values():
                    if isinstance(value, list):
                        expanded.extend(value)
                    elif isinstance(value, dict):
                        expanded.append(value)

                combos = expanded

        if not isinstance(combos, list):
            return 0, []

        for combo in combos:
            if not isinstance(combo, dict):
                continue

            champions = combo.get("champions", [])

            if not isinstance(champions, list):
                continue

            champions = [
                clean_champion_id(champ)
                for champ in champions
                if clean_champion_id(champ)
            ]

            if candidate_id not in champions:
                continue

            matched_allies = [
                champ
                for champ in champions
                if champ in ally_set and champ != candidate_id
            ]

            if not matched_allies:
                continue

            raw_score = combo.get("score", 6)

            weight = calc_weight(
                raw_score,
                confidence=combo.get("confidence", "unknown"),
                source_type=combo.get("source_type", ""),
                default=4,
            )

            # 阵容配合不能压过 counter，压缩一下。
            weight = max(1, min(6, round(weight / 2)))

            score += weight

            matched_names = "、".join(
                self.get_display_name(champ)
                for champ in matched_allies
            )

            reason = combo.get("reason", "")

            reasons.append(
                f"和我方 {matched_names} 有阵容配合 +{weight}：{reason}"
            )

        return score, reasons

    def _score_champion_strength(
        self,
        candidate_id: str,
        target_role: str | None = None,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        data = self.champion_strength

        if isinstance(data, dict):
            data = data.get("champions", [])

        if not isinstance(data, list):
            return 0, []

        target_role = normalize_role(target_role)

        for item in data:
            if not isinstance(item, dict):
                continue

            champion = clean_champion_id(item.get("champion"))

            if champion != candidate_id:
                continue

            item_role = normalize_role(item.get("role"))

            if target_role and item_role and item_role != target_role:
                continue

            raw_score = item.get("score", item.get("strength_score", 0))

            weight = calc_weight(
                raw_score,
                confidence=item.get("confidence", "unknown"),
                source_type=item.get("source_type", ""),
                default=2,
            )

            # 英雄强度只是辅助，不要压过 counter。
            weight = max(1, min(4, round(weight / 2)))

            score += weight

            reason = item.get("reason", "")

            if reason:
                reasons.append(
                    f"当前强度参考 +{weight}：{reason}"
                )
            else:
                reasons.append(
                    f"当前强度参考 +{weight}"
                )

        return score, reasons