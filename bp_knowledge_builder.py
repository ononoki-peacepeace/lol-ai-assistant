from __future__ import annotations

from config import (
    COUNTERS_PATH,
    COMPOSITIONS_PATH,
    CHAMPION_TAGS_PATH,
    load_json,
)

CHAMPION_STRENGTH_PATH = "knowledge/bp/champion_strength.json"
TEAM_COMBOS_PATH = "knowledge/bp/team_combos.json"


class BPKnowledgeBuilder:
    def __init__(self):
        self.counters = load_json(COUNTERS_PATH, default={})
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})
        self.champion_strength = load_json(CHAMPION_STRENGTH_PATH, default=[])
        self.team_combos = load_json(TEAM_COMBOS_PATH, default=[])

    def build_candidate_evidence(
        self,
        candidate_id: str,
        ally_picks: list[str],
        enemy_picks: list[str],
        target_role: str | None = None,
        lane_opponent: str | None = None,
    ) -> dict:
        evidence = []

        evidence.extend(
            self._find_counter_evidence(
                candidate_id=candidate_id,
                enemy_picks=enemy_picks,
                lane_opponent=lane_opponent,
            )
        )

        evidence.extend(
            self._find_team_combo_evidence(
                candidate_id=candidate_id,
                ally_picks=ally_picks,
            )
        )

        evidence.extend(
            self._find_strength_evidence(
                candidate_id=candidate_id,
                target_role=target_role,
            )
        )

        evidence.extend(
            self._find_tag_evidence(
                candidate_id=candidate_id,
                ally_picks=ally_picks,
                enemy_picks=enemy_picks,
            )
        )

        evidence_score = sum(
            int(item.get("importance", 0))
            for item in evidence
        )

        return {
            "champion": candidate_id,
            "evidence_score": evidence_score,
            "evidence": evidence,
        }

    def _find_counter_evidence(
        self,
        candidate_id: str,
        enemy_picks: list[str],
        lane_opponent: str | None = None,
    ) -> list[dict]:
        result = []
        enemy_set = {x for x in enemy_picks if x and x != "暂无"}

        # 1. 候选英雄视角：candidate.good_against enemy
        candidate_info = self.counters.get(candidate_id, {})

        if isinstance(candidate_info, dict):
            for item in candidate_info.get("good_against", []):
                enemy = item.get("champion")

                if enemy not in enemy_set:
                    continue

                importance = int(item.get("importance", abs(int(item.get("score", 3))) + 4))

                if lane_opponent and enemy == lane_opponent:
                    importance += 2

                result.append({
                    "type": "counter",
                    "direction": "candidate_good_against_enemy",
                    "target": enemy,
                    "importance": importance,
                    "reason": item.get("reason", ""),
                    "source_type": item.get("source_type", ""),
                    "confidence": item.get("confidence", "unknown"),
                })

            for item in candidate_info.get("bad_against", []):
                enemy = item.get("champion")

                if enemy not in enemy_set:
                    continue

                importance = -abs(int(item.get("importance", abs(int(item.get("score", -3))) + 4)))

                if lane_opponent and enemy == lane_opponent:
                    importance -= 2

                result.append({
                    "type": "counter_risk",
                    "direction": "candidate_bad_against_enemy",
                    "target": enemy,
                    "importance": importance,
                    "reason": item.get("reason", ""),
                    "source_type": item.get("source_type", ""),
                    "confidence": item.get("confidence", "unknown"),
                })

        # 2. 敌方英雄视角：enemy.bad_against candidate
        for enemy in enemy_set:
            enemy_info = self.counters.get(enemy, {})

            if not isinstance(enemy_info, dict):
                continue

            for item in enemy_info.get("bad_against", []):
                if item.get("champion") != candidate_id:
                    continue

                importance = int(item.get("importance", abs(int(item.get("score", -3))) + 4))

                if lane_opponent and enemy == lane_opponent:
                    importance += 2

                result.append({
                    "type": "counter",
                    "direction": "enemy_bad_against_candidate",
                    "target": enemy,
                    "importance": importance,
                    "reason": item.get("reason", ""),
                    "source_type": item.get("source_type", ""),
                    "confidence": item.get("confidence", "unknown"),
                })

            for item in enemy_info.get("good_against", []):
                if item.get("champion") != candidate_id:
                    continue

                importance = -abs(int(item.get("importance", abs(int(item.get("score", 3))) + 4)))

                if lane_opponent and enemy == lane_opponent:
                    importance -= 2

                result.append({
                    "type": "counter_risk",
                    "direction": "enemy_good_against_candidate",
                    "target": enemy,
                    "importance": importance,
                    "reason": item.get("reason", ""),
                    "source_type": item.get("source_type", ""),
                    "confidence": item.get("confidence", "unknown"),
                })

        return result

    def _find_team_combo_evidence(
        self,
        candidate_id: str,
        ally_picks: list[str],
    ) -> list[dict]:
        result = []
        ally_set = {x for x in ally_picks if x and x != "暂无"}

        if not isinstance(self.team_combos, list):
            return result

        for combo in self.team_combos:
            champions = combo.get("champions", [])

            if candidate_id not in champions:
                continue

            matched_allies = [
                champ for champ in champions
                if champ in ally_set and champ != candidate_id
            ]

            if not matched_allies:
                continue

            result.append({
                "type": "team_combo",
                "combo_type": combo.get("combo_type", ""),
                "matched_allies": matched_allies,
                "importance": int(combo.get("importance", combo.get("score", 6))),
                "reason": combo.get("reason", ""),
                "confidence": combo.get("confidence", "unknown"),
                "source_type": combo.get("source_type", ""),
            })

        return result

    def _find_strength_evidence(
        self,
        candidate_id: str,
        target_role: str | None = None,
    ) -> list[dict]:
        result = []

        if not isinstance(self.champion_strength, list):
            return result

        for item in self.champion_strength:
            if item.get("champion") != candidate_id:
                continue

            if target_role and item.get("role") and item.get("role") != target_role:
                continue

            result.append({
                "type": "champion_strength",
                "role": item.get("role", ""),
                "importance": int(item.get("importance", item.get("score", 5))),
                "strength_score": item.get("score", item.get("strength_score", 0)),
                "score_type": item.get("score_type", ""),
                "reason": item.get("reason", ""),
                "confidence": item.get("confidence", "unknown"),
                "source_type": item.get("source_type", ""),
            })

        return result

    def _find_tag_evidence(
        self,
        candidate_id: str,
        ally_picks: list[str],
        enemy_picks: list[str],
    ) -> list[dict]:
        tags = self.champion_tags.get(candidate_id, [])

        if not tags:
            return []

        evidence = []

        # 简单版：先只把标签给 AI，后面再做阵容缺口判断
        evidence.append({
            "type": "champion_tags",
            "importance": 3,
            "tags": tags,
            "reason": f"{candidate_id} 的本地标签：{', '.join(tags)}"
        })

        return evidence

    def build_bp_evidence(
        self,
        candidate_ids: list[str],
        ally_picks: list[str],
        enemy_picks: list[str],
        target_role: str | None = None,
        lane_opponent: str | None = None,
    ) -> dict:
        candidates = []

        for candidate_id in candidate_ids:
            item = self.build_candidate_evidence(
                candidate_id=candidate_id,
                ally_picks=ally_picks,
                enemy_picks=enemy_picks,
                target_role=target_role,
                lane_opponent=lane_opponent,
            )
            candidates.append(item)

        candidates.sort(
            key=lambda x: x.get("evidence_score", 0),
            reverse=True,
        )

        return {
            "bp_state": {
                "ally_picks": ally_picks,
                "enemy_picks": enemy_picks,
                "target_role": target_role,
                "lane_opponent": lane_opponent,
            },
            "candidates": candidates,
        }