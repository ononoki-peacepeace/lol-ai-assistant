from collections import Counter

from config import (
    CHAMPIONS_PATH,
    CHAMPION_TAGS_PATH,
    COUNTERS_PATH,
    SYNERGIES_PATH,
    COMPOSITIONS_PATH,
    load_json,
)


class ChampionRecommender:
    def __init__(self):
        self.champions = load_json(CHAMPIONS_PATH, default={})
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})
        self.counters = load_json(COUNTERS_PATH, default={})
        self.synergies = load_json(SYNERGIES_PATH, default={})
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
            counter_score, counter_reasons = self._score_counters(champion_id, enemy_picks)
            score += counter_score
            score_reasons.extend(counter_reasons)

            # 4. 己方配合加分
            synergy_score, synergy_reasons = self._score_synergies(champion_id, ally_picks)
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

    def _score_counters(self, candidate_id: str, enemy_picks: list[str]) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        info = self.counters.get(candidate_id, {})

        for item in info.get("good_against", []):
            enemy = item.get("champion")
            if enemy in enemy_picks:
                value = int(item.get("score", 0))
                score += value
                reasons.append(
                    f"对敌方 {self.get_display_name(enemy)} 有克制关系 +{value}：{item.get('reason', '')}"
                )

        for item in info.get("bad_against", []):
            enemy = item.get("champion")
            if enemy in enemy_picks:
                value = int(item.get("score", -1))
                score += value
                reasons.append(
                    f"面对敌方 {self.get_display_name(enemy)} 有风险 {value}：{item.get('reason', '')}"
                )

        return score, reasons

    def _score_synergies(self, candidate_id: str, ally_picks: list[str]) -> tuple[int, list[str]]:
        score = 0
        reasons = []
        seen_pairs = set()

        # 情况 A：candidate 自己配置了 good_with
        candidate_info = self.synergies.get(candidate_id, {})
        for item in candidate_info.get("good_with", []):
            ally = item.get("champion")
            if ally in ally_picks:
                pair_key = tuple(sorted([candidate_id, ally]))
                if pair_key in seen_pairs:
                    continue

                seen_pairs.add(pair_key)
                value = int(item.get("score", 0))
                score += value
                reasons.append(
                    f"和己方 {self.get_display_name(ally)} 有配合 +{value}：{item.get('reason', '')}"
                )

        # 情况 B：己方英雄配置了 good_with candidate
        for ally in ally_picks:
            ally_info = self.synergies.get(ally, {})
            for item in ally_info.get("good_with", []):
                if item.get("champion") == candidate_id:
                    pair_key = tuple(sorted([candidate_id, ally]))
                    if pair_key in seen_pairs:
                        continue

                    seen_pairs.add(pair_key)
                    value = int(item.get("score", 0))
                    score += value
                    reasons.append(
                        f"和己方 {self.get_display_name(ally)} 有配合 +{value}：{item.get('reason', '')}"
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