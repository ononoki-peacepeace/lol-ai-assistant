import json
from pathlib import Path
from collections import Counter


BASE_DIR = Path(__file__).resolve().parent

CHAMPIONS_PATH = BASE_DIR / "data" / "champions.json"
TAGS_PATH = BASE_DIR / "data" / "champion_tags.json"
PICK_RULES_PATH = BASE_DIR / "rules" / "bp" / "pick_rules.json"


class BPAnalyzer:
    def __init__(self):
        self.champions = self._load_json(CHAMPIONS_PATH)
        self.champion_tags = self._load_json(TAGS_PATH)
        self.pick_rules = self._load_json(PICK_RULES_PATH)

    def _load_json(self, path: Path):
        if not path.exists():
            print(f"[警告] 文件不存在: {path}")
            return [] if path.name.endswith("rules.json") else {}

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_display_name(self, champion_id: str) -> str:
        info = self.champions.get(champion_id, {})
        return info.get("title") or info.get("name") or champion_id

    def get_tags(self, champion_id: str) -> list[str]:
        return self.champion_tags.get(champion_id, [])

    def count_tags(self, picks: list[str]) -> Counter:
        counter = Counter()

        for champion_id in picks:
            if not champion_id:
                continue

            for tag in self.get_tags(champion_id):
                counter[tag] += 1

        return counter

    def analyze(self, ally_picks: list[str], enemy_picks: list[str]) -> dict:
        ally_tags = self.count_tags(ally_picks)
        enemy_tags = self.count_tags(enemy_picks)

        triggered_rules = []

        for rule in self.pick_rules:
            if self._match_rule(rule, ally_tags, enemy_tags):
                triggered_rules.append(rule)

        return {
            "ally_picks": ally_picks,
            "enemy_picks": enemy_picks,
            "ally_display_picks": [self.get_display_name(x) for x in ally_picks if x],
            "enemy_display_picks": [self.get_display_name(x) for x in enemy_picks if x],
            "ally_tags": dict(ally_tags),
            "enemy_tags": dict(enemy_tags),
            "triggered_rules": triggered_rules,
        }

    def _match_rule(self, rule: dict, ally_tags: Counter, enemy_tags: Counter) -> bool:
        condition = rule.get("condition", {})

        # 支持 ally_tag / enemy_tag
        # 也支持 ally_tag_2 / enemy_tag_2 这种追加条件
        index = 1

        while True:
            suffix = "" if index == 1 else f"_{index}"

            ally_tag_key = f"ally_tag{suffix}"
            enemy_tag_key = f"enemy_tag{suffix}"
            min_count_key = f"min_count{suffix}"
            max_count_key = f"max_count{suffix}"

            has_condition = (
                ally_tag_key in condition
                or enemy_tag_key in condition
                or min_count_key in condition
                or max_count_key in condition
            )

            if not has_condition:
                break

            if ally_tag_key in condition:
                tag = condition[ally_tag_key]
                count = ally_tags.get(tag, 0)

                if min_count_key in condition and count < condition[min_count_key]:
                    return False

                if max_count_key in condition and count > condition[max_count_key]:
                    return False

            if enemy_tag_key in condition:
                tag = condition[enemy_tag_key]
                count = enemy_tags.get(tag, 0)

                if min_count_key in condition and count < condition[min_count_key]:
                    return False

                if max_count_key in condition and count > condition[max_count_key]:
                    return False

            index += 1

        return True

    def format_analysis(self, analysis: dict) -> str:
        lines = []

        lines.append("===== BP 分析结果 =====")
        lines.append("")
        lines.append("己方 Pick：" + "、".join(analysis["ally_display_picks"] or ["暂无"]))
        lines.append("敌方 Pick：" + "、".join(analysis["enemy_display_picks"] or ["暂无"]))
        lines.append("")

        lines.append("己方标签：")
        lines.extend(self._format_tags(analysis["ally_tags"]))
        lines.append("")

        lines.append("敌方标签：")
        lines.extend(self._format_tags(analysis["enemy_tags"]))
        lines.append("")

        lines.append("触发的 BP 规则：")
        if not analysis["triggered_rules"]:
            lines.append("- 暂无明确建议")
        else:
            for rule in analysis["triggered_rules"]:
                advice = rule.get("recommend", {})
                lines.append(f"- [{rule.get('priority', 'normal')}] {rule.get('name', rule.get('id'))}")
                lines.append(f"  建议：{advice.get('short', '')}")
                lines.append(f"  原因：{advice.get('reason', '')}")

        return "\n".join(lines)

    def _format_tags(self, tags: dict) -> list[str]:
        if not tags:
            return ["- 暂无"]

        sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
        return [f"- {tag}: {count}" for tag, count in sorted_tags]