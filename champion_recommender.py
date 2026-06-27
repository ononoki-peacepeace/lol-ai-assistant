import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

CHAMPIONS_PATH = BASE_DIR / "data" / "champions.json"
TAGS_PATH = BASE_DIR / "data" / "champion_tags.json"


class ChampionRecommender:
    def __init__(self):
        self.champions = self._load_json(CHAMPIONS_PATH)
        self.champion_tags = self._load_json(TAGS_PATH)

    def _load_json(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_display_name(self, champion_id: str) -> str:
        info = self.champions.get(champion_id, {})
        return info.get("title") or info.get("name") or champion_id

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

        # 从触发规则里收集推荐标签
        wanted_tags = []
        for rule in triggered_rules:
            recommend = rule.get("recommend", {})
            wanted_tags.extend(recommend.get("tags", []))

        wanted_tags = list(dict.fromkeys(wanted_tags))

        results = []

        for champion_id, tags in self.champion_tags.items():
            if champion_id in unavailable:
                continue

            # 如果指定位置，就必须包含这个位置标签
            if target_role and target_role not in tags:
                continue

            score = 0
            matched_tags = []

            for tag in wanted_tags:
                if tag in tags:
                    score += 2
                    matched_tags.append(tag)

            # 位置匹配加分
            if target_role and target_role in tags:
                score += 3

            if score <= 0:
                continue

            results.append({
                "id": champion_id,
                "name": self.get_display_name(champion_id),
                "score": score,
                "matched_tags": matched_tags,
                "all_tags": tags,
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_n]