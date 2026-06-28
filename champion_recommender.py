from collections import Counter

from config import (
    CHAMPIONS_PATH,
    CHAMPION_TAGS_PATH,
    COUNTERS_PATH,
    team_combo_PATH,
    COMPOSITIONS_PATH,
    load_json,
)


class ChampionRecommender:
    def __init__(self):
        self.champions = load_json(CHAMPIONS_PATH, default={})
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})
        self.counters = load_json(COUNTERS_PATH, default={})
        self.team_combo = load_json(team_combo_PATH, default={})
        self.compositions = load_json(COMPOSITIONS_PATH, default=[])

    def get_display_name(self, champion_id: str) -> str:
        info = self.champions.get(champion_id, {})
        return info.get("title") or info.get("name") or champion_id

    def get_tags(self, champion_id: str) -> list[str]:
        return self.champion_tags.get(champion_id, [])

    def recommend(
        self,
        triggered_rules: list[dict],
        target_role: str | None = None,
        ally_picks: list[str] | None = None,
        enemy_picks: list[str] | None = None,
        banned_champions: list[str] | None = None,
        lane_opponent: str | None = None,
        lane_opponent_confidence: str = "unknown",
        top_n: int = 8,
    ) -> list[dict]:
        ally_picks = ally_picks or []
        enemy_picks = enemy_picks or []
        banned_champions = banned_champions or []

        unavailable = set(ally_picks + enemy_picks + banned_champions)

        wanted_tags = self._collect_wanted_tags(triggered_rules)
        ally_tag_counter = self._count_team_tags(ally_picks)

        results = []

        for champion_id, tags in self.champion_tags.items():
            if champion_id in unavailable:
                continue

            if target_role and target_role not in tags:
                continue

            score = 0
            matched_tags = []
            score_reasons = []

            # 1. 目标位置加分
            if target_role and target_role in tags:
                score += 3
                score_reasons.append(f"符合目标位置：{target_role} +3")

            # 2. BP 规则推荐 tag 加分
            for tag in wanted_tags:
                if tag in tags:
                    score += 2
                    matched_tags.append(tag)
                    score_reasons.append(f"命中推荐标签：{tag} +2")

            # 3. 康特关系加分 / 扣分
            counter_score, counter_reasons = self._score_counters(
            candidate_id=champion_id,
            enemy_picks=enemy_picks,
            lane_opponent=lane_opponent,
            lane_opponent_confidence=lane_opponent_confidence,
            )
            score += counter_score
            score_reasons.extend(counter_reasons)

            # 4. 己方配合加分
            synergy_score, synergy_reasons = self._score_team_combo(champion_id, ally_picks)
            score += synergy_score
            score_reasons.extend(synergy_reasons)

            # 5. 阵容体系加分
            comp_score, comp_reasons = self._score_compositions(tags, ally_tag_counter)
            score += comp_score
            score_reasons.extend(comp_reasons)

            if score <= 0:
                continue

            results.append(
                {
                    "id": champion_id,
                    "name": self.get_display_name(champion_id),
                    "score": score,
                    "matched_tags": matched_tags,
                    "all_tags": tags,
                    "score_reasons": score_reasons,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def _collect_wanted_tags(self, triggered_rules: list[dict]) -> list[str]:
        wanted_tags = []

        for rule in triggered_rules:
            recommend = rule.get("recommend", {})
            wanted_tags.extend(recommend.get("tags", []))

        # 去重但保持顺序
        return list(dict.fromkeys(wanted_tags))

    def _count_team_tags(self, picks: list[str]) -> Counter:
        counter = Counter()

        for champion_id in picks:
            for tag in self.get_tags(champion_id):
                counter[tag] += 1

        return counter

    def _score_counters(
        self,
        candidate_id: str,
        enemy_picks: list[str],
        lane_opponent: str | None = None,
        lane_opponent_confidence: str = "unknown",
    ) -> tuple[int, list[str]]:
        """
        counter 评分。

        同时支持两种写法：

        1. 候选英雄视角：
        Poppy.good_against Aatrox
        表示我选 Poppy 打 Aatrox 有优势。

        2. 敌方英雄视角：
        Aatrox.bad_against Poppy
        也表示我选 Poppy 打 Aatrox 有优势。

        这样就不会因为 JSON 方向不同导致 counter 完全不生效。
        """
        score = 0
        reasons = []

        enemy_set = {
            enemy
            for enemy in enemy_picks
            if enemy and enemy != "暂无"
        }

        if not enemy_set:
            return 0, []

        used_relations = set()

        def is_lane_enemy(enemy_id: str) -> bool:
            return bool(lane_opponent and enemy_id == lane_opponent)

        def lane_bonus(enemy_id: str) -> int:
            if is_lane_enemy(enemy_id):
                return 2
            return 0

        # =========================================================
        # 1. 直接查候选英雄视角：
        # candidate.good_against enemy
        # candidate.bad_against enemy
        # =========================================================
        candidate_info = self.counters.get(candidate_id, {})

        if isinstance(candidate_info, dict):
            for item in candidate_info.get("good_against", []):
                enemy = item.get("champion")
                if enemy not in enemy_set:
                    continue

                relation_key = (candidate_id, enemy, "positive")
                if relation_key in used_relations:
                    continue
                used_relations.add(relation_key)

                try:
                    base_value = abs(int(item.get("score", 0)))
                except (TypeError, ValueError):
                    base_value = 0

                value = base_value + lane_bonus(enemy)
                score += value

                if is_lane_enemy(enemy):
                    reasons.append(
                        f"预计对线 {self.get_display_name(enemy)}，且本地库显示 "
                        f"{self.get_display_name(candidate_id)} 对该英雄有优势 +{value}："
                        f"{item.get('reason', '')}"
                    )
                else:
                    reasons.append(
                        f"对敌方 {self.get_display_name(enemy)} 有 counter 价值 +{value}："
                        f"{item.get('reason', '')}"
                    )

            for item in candidate_info.get("bad_against", []):
                enemy = item.get("champion")
                if enemy not in enemy_set:
                    continue

                relation_key = (candidate_id, enemy, "negative")
                if relation_key in used_relations:
                    continue
                used_relations.add(relation_key)

                try:
                    base_value = -abs(int(item.get("score", -1)))
                except (TypeError, ValueError):
                    base_value = -1

                value = base_value - lane_bonus(enemy)
                score += value

                if is_lane_enemy(enemy):
                    reasons.append(
                        f"预计对线 {self.get_display_name(enemy)}，但本地库显示 "
                        f"{self.get_display_name(candidate_id)} 这个对位有风险 {value}："
                        f"{item.get('reason', '')}"
                    )
                else:
                    reasons.append(
                        f"面对敌方 {self.get_display_name(enemy)} 有风险 {value}："
                        f"{item.get('reason', '')}"
                    )

        # =========================================================
        # 2. 反向查敌方英雄视角：
        # enemy.bad_against candidate  => candidate 打 enemy 有优势
        # enemy.good_against candidate => candidate 打 enemy 有风险
        # =========================================================
        for enemy in enemy_set:
            enemy_info = self.counters.get(enemy, {})

            if not isinstance(enemy_info, dict):
                continue

            # enemy.bad_against candidate
            # 例：Aatrox.bad_against Poppy
            # 含义：Poppy 打 Aatrox 有优势
            for item in enemy_info.get("bad_against", []):
                target = item.get("champion")
                if target != candidate_id:
                    continue

                relation_key = (candidate_id, enemy, "positive")
                if relation_key in used_relations:
                    continue
                used_relations.add(relation_key)

                try:
                    base_value = abs(int(item.get("score", -1)))
                except (TypeError, ValueError):
                    base_value = 1

                value = base_value + lane_bonus(enemy)
                score += value

                if is_lane_enemy(enemy):
                    reasons.append(
                        f"预计对线 {self.get_display_name(enemy)}，且本地库显示 "
                        f"{self.get_display_name(enemy)} 害怕 {self.get_display_name(candidate_id)} +{value}："
                        f"{item.get('reason', '')}"
                    )
                else:
                    reasons.append(
                        f"敌方 {self.get_display_name(enemy)} 被 "
                        f"{self.get_display_name(candidate_id)} 克制 +{value}："
                        f"{item.get('reason', '')}"
                    )

            # enemy.good_against candidate
            # 例：Aatrox.good_against Poppy
            # 含义：Poppy 打 Aatrox 有风险
            for item in enemy_info.get("good_against", []):
                target = item.get("champion")
                if target != candidate_id:
                    continue

                relation_key = (candidate_id, enemy, "negative")
                if relation_key in used_relations:
                    continue
                used_relations.add(relation_key)

                try:
                    base_value = -abs(int(item.get("score", 1)))
                except (TypeError, ValueError):
                    base_value = -1

                value = base_value - lane_bonus(enemy)
                score += value

                if is_lane_enemy(enemy):
                    reasons.append(
                        f"预计对线 {self.get_display_name(enemy)}，但本地库显示 "
                        f"{self.get_display_name(enemy)} 对 {self.get_display_name(candidate_id)} 有优势 {value}："
                        f"{item.get('reason', '')}"
                    )
                else:
                    reasons.append(
                        f"面对敌方 {self.get_display_name(enemy)} 有 counter 风险 {value}："
                        f"{item.get('reason', '')}"
                    )

        return score, reasons

    def _score_team_combo(self, candidate_id: str, ally_picks: list[str]) -> tuple[int, list[str]]:
        """
        根据 team_combos.json 计算候选英雄和我方已选英雄的配合分。

        team_combos.json 当前格式是 list：
        [
        {
            "champions": ["Malphite", "Yasuo"],
            "score": 9,
            "reason": "..."
        }
        ]
        """
        score = 0
        reasons = []

        ally_set = {
            champ
            for champ in ally_picks
            if champ and champ != "暂无"
        }

        if not ally_set:
            return 0, []

        combos = self.team_combo

        # 兼容旧格式：如果以后或以前有人写成 dict，也尽量展开成 list
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

            # 候选英雄必须在这个 combo 里
            if candidate_id not in champions:
                continue

            # 这个 combo 里还必须至少有一个我方已选英雄
            matched_allies = [
                champ
                for champ in champions
                if champ in ally_set and champ != candidate_id
            ]

            if not matched_allies:
                continue

            try:
                raw_score = int(combo.get("score", 0))
            except (TypeError, ValueError):
                raw_score = 0

            # team_combo 原始 score 通常是 7/8/9，推荐系统里不要一次加太爆
            value = max(1, min(5, round(raw_score / 2)))

            score += value

            matched_names = "、".join(
                self.get_display_name(champ)
                for champ in matched_allies
            )

            reason = combo.get("reason", "")

            reasons.append(
                f"和我方 {matched_names} 有阵容配合 +{value}：{reason}"
            )

        return score, reasons
    def _score_compositions(self, candidate_tags: list[str], ally_tag_counter: Counter) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        ally_tags = set(ally_tag_counter.keys())
        candidate_tag_set = set(candidate_tags)
        combined_tags = ally_tags | candidate_tag_set

        for comp in self.compositions:
            required_tags = set(comp.get("required_tags", []))
            bonus_tags = set(comp.get("bonus_tags", []))

            if not required_tags:
                continue

            missing_before = required_tags - ally_tags
            missing_after = required_tags - combined_tags

            filled_tags = missing_before - missing_after

            if filled_tags:
                value = len(filled_tags) * 2
                score += value
                reasons.append(
                    f"帮助靠近「{comp.get('name', comp.get('id'))}」体系，补足 {list(filled_tags)} +{value}"
                )

            # 如果已经满足体系，候选还能补 bonus tag，少量加分
            if not missing_after:
                matched_bonus = candidate_tag_set & bonus_tags
                if matched_bonus:
                    value = len(matched_bonus)
                    score += value
                    reasons.append(
                        f"强化「{comp.get('name', comp.get('id'))}」体系 bonus 标签 {list(matched_bonus)} +{value}"
                    )

        return score, reasons