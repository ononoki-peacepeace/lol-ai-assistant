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
        lines = []

        lines.append("请根据以下 BP 信息，从候选英雄中给出推荐。")
        lines.append("")

        if target_role:
            lines.append(f"目标位置：{target_role}")
            lines.append("")

        lines.append("己方英雄：")
        lines.append("、".join(analysis.get("ally_display_picks", []) or ["暂无"]))
        lines.append("")

        lines.append("敌方英雄：")
        lines.append("、".join(analysis.get("enemy_display_picks", []) or ["暂无"]))
        lines.append("")

        lines.append("已触发规则：")
        triggered_rules = analysis.get("triggered_rules", [])
        if not triggered_rules:
            lines.append("- 暂无")
        else:
            for rule in triggered_rules:
                recommend = rule.get("recommend", {})
                lines.append(
                    f"- {rule.get('name')}: "
                    f"{recommend.get('short')} "
                    f"原因：{recommend.get('reason')}"
                )

        lines.append("")
        lines.append("候选英雄：")
        if not recommendations:
            lines.append("- 暂无候选英雄")
        else:
            for index, item in enumerate(recommendations, start=1):
                lines.append(
                    f"{index}. {item['name']}({item['id']})，"
                    f"命中标签：{item['matched_tags']}，"
                    f"全部标签：{item['all_tags']}，"
                    f"分数：{item['score']}"
                )

        lines.append("")
        lines.append("输出要求：")
        lines.append("1. 只能从候选英雄中推荐，不要提到候选外英雄。")
        lines.append("2. 给出首推 1 个英雄，备选 2 个英雄。")
        lines.append("3. 每个英雄说明适合原因和简单风险。")
        lines.append("4. 不要超过 220 字。")
        lines.append("5. 适合 BP 阶段快速阅读。")

        return "\n".join(lines)