from config import CHARACTERS_DIR, LLM_CONFIG_PATH, load_json
from llm_client import LLMClient


class AICommentator:
    def __init__(self):
        self.llm = LLMClient()

        llm_config = load_json(LLM_CONFIG_PATH, default={})
        character_id = llm_config.get("character_card", "default_assistant")

        character_path = CHARACTERS_DIR / f"{character_id}.json"
        self.character = load_json(character_path, default={})

    def explain_bp(self, analysis: dict, recommendations: list[dict], target_role: str | None = None) -> str:
        prompt = self._build_prompt(analysis, recommendations, target_role)
        
        system_prompt = self._build_system_prompt()

        return self.llm.chat([
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ])

    def _build_system_prompt(self) -> str:
        base_prompt = self.character.get(
            "system_prompt",
            "你是一个英雄联盟 BP 推荐助手。"
        )

        rules = self.character.get("rules", [])
        output_style = self.character.get("output_style", "")

        lines = [base_prompt]

        if rules:
            lines.append("")
            lines.append("你必须遵守以下规则：")
            for rule in rules:
                lines.append(f"- {rule}")

        if output_style:
            lines.append("")
            lines.append(f"输出风格：{output_style}")

        return "\n".join(lines)

    def _build_prompt(self, analysis: dict, recommendations: list[dict], target_role: str | None = None) -> str:
        ally_picks = analysis.get("ally_display_picks", analysis.get("ally_picks", []))
        enemy_picks = analysis.get("enemy_display_picks", analysis.get("enemy_picks", []))
        triggered_rules = analysis.get("triggered_rules", [])

        rule_lines = []
        for rule in triggered_rules:
            recommend = rule.get("recommend", {})
            rule_lines.append(
                f"- {rule.get('name', rule.get('id', '未知规则'))}: "
                f"{recommend.get('short', '')}"
            )

        def build_natural_points(item: dict) -> list[str]:
            name = item.get("name", item.get("id"))
            tags = item.get("all_tags", [])
            matched_tags = item.get("matched_tags", [])
            raw_reasons = item.get("score_reasons", [])

            natural_points = []

            if target_role and target_role in tags:
                natural_points.append(f"{name}适合当前目标位置：{target_role}")

            if matched_tags:
                natural_points.append(f"{name}能补到阵容需要的能力：{'、'.join(matched_tags)}")

            for reason in raw_reasons:
                if "有克制关系" in reason:
                    text = reason.split("：", 1)[-1] if "：" in reason else reason
                    natural_points.append(f"{name}对敌方部分英雄处理能力不错：{text}")

                elif "有风险" in reason:
                    text = reason.split("：", 1)[-1] if "：" in reason else reason
                    natural_points.append(f"{name}也有风险：{text}")

                elif "有配合" in reason:
                    text = reason.split("：", 1)[-1] if "：" in reason else reason
                    natural_points.append(f"{name}和己方阵容有配合：{text}")

                elif "帮助靠近" in reason or "强化" in reason:
                    clean_text = (
                        reason
                        .replace("+1", "")
                        .replace("+2", "")
                        .replace("+3", "")
                        .replace("+4", "")
                        .replace("+5", "")
                    )
                    natural_points.append(f"{name}{clean_text}")

            return list(dict.fromkeys(natural_points))

        if not recommendations:
            return "当前没有可推荐英雄。"

        main_pick = recommendations[0]
        backup_picks = recommendations[:10]

        main_name = main_pick.get("name", main_pick.get("id"))
        main_id = main_pick.get("id")
        main_points = build_natural_points(main_pick)

        backup_lines = []
        for idx, item in enumerate(backup_picks, start=1):
            name = item.get("name", item.get("id"))
            champion_id = item.get("id")
            points = build_natural_points(item)

            backup_lines.append(
                f"{idx}. {name}({champion_id})\n"
                f"   适合点：{'；'.join(points[:4]) if points else '可以作为同类型备选'}"
            )

        prompt = f"""
        当前是英雄联盟 BP 阶段。

        目标位置：
        {target_role or "未知"}

        己方已选：
        {ally_picks}

        敌方已选：
        {enemy_picks}

        当前 BP 判断：
        {chr(10).join(rule_lines) if rule_lines else "暂无"}

        程序已经排好推荐顺序，请不要重新判断候选数量，也不要说“只有一个候选”。

        首推英雄，必须解释：
        {main_name}({main_id})
        适合点：
        {chr(10).join("- " + p for p in main_points) if main_points else "暂无明确说明"}

        备选英雄，数量为5到7个，必须分别解释：
        {chr(10).join(backup_lines) if backup_lines else "暂无备选"}

        请你像一个懂 BP 的队友一样，把上面的信息整理成人话。

        要求：
        1. 必须首推 {main_name}。
        2. 不要输出分数、+3、+2、命中标签、程序判断这类调试信息。
        3. 不要逐条复述适合点，要整合成自然语言。
        4. 如果首推有明显风险，要自然提醒。
        5. 不要编造没有提供的信息。
        6. 输出控制在 500 字以内。

        
        """.strip()

        return prompt