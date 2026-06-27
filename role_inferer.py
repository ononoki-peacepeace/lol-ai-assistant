from config import CHAMPION_TAGS_PATH, load_json


ROLES = ["上单", "打野", "中单", "下路", "辅助"]

ROLE_ALIASES = {
    "top": "上单",
    "上路": "上单",
    "上单": "上单",

    "jungle": "打野",
    "jg": "打野",
    "野区": "打野",
    "打野": "打野",

    "mid": "中单",
    "middle": "中单",
    "中路": "中单",
    "中单": "中单",

    "adc": "下路",
    "bot": "下路",
    "bottom": "下路",
    "下路": "下路",

    "support": "辅助",
    "sup": "辅助",
    "辅助": "辅助",
}


class RoleInferer:
    def __init__(self):
        self.champion_tags = load_json(CHAMPION_TAGS_PATH, default={})

    def normalize_role(self, role: str | None) -> str | None:
        if role is None:
            return None
        return ROLE_ALIASES.get(role, role)

    def get_roles(self, champion_id: str) -> list[str]:
        tags = self.champion_tags.get(champion_id, [])
        roles = []

        for tag in tags:
            normalized = self.normalize_role(tag)
            if normalized in ROLES and normalized not in roles:
                roles.append(normalized)

        return roles

    def infer_team_roles(self, picks: list[str]) -> dict:
        result = {}
        unknown = []
        used = set()

        champion_roles = {}

        for champ in picks:
            roles = self.get_roles(champ)
            champion_roles[champ] = roles

            if not roles:
                unknown.append({
                    "champion": champ,
                    "reason": "没有位置标签"
                })

        # 第一轮：只有一个位置标签的英雄，直接确定
        for champ, roles in champion_roles.items():
            if champ in used:
                continue

            if len(roles) == 1:
                role = roles[0]

                if role not in result:
                    result[role] = {
                        "champion": champ,
                        "confidence": "high"
                    }
                    used.add(champ)
                else:
                    unknown.append({
                        "champion": champ,
                        "possible_roles": roles,
                        "reason": f"{role} 已经被 {result[role]['champion']} 占用"
                    })

        # 第二轮：多位置英雄，如果只剩一个空位能放，就中等置信度确定
        changed = True
        while changed:
            changed = False

            for champ, roles in champion_roles.items():
                if champ in used:
                    continue

                available_roles = [
                    role for role in roles
                    if role not in result
                ]

                if len(available_roles) == 1:
                    role = available_roles[0]
                    result[role] = {
                        "champion": champ,
                        "confidence": "medium"
                    }
                    used.add(champ)
                    changed = True

        # 剩下无法确定的
        for champ, roles in champion_roles.items():
            if champ in used:
                continue

            if roles:
                unknown.append({
                    "champion": champ,
                    "possible_roles": roles,
                    "reason": "多位置或位置冲突，无法确定"
                })

        if unknown:
            result["unknown"] = unknown

        return result

    def get_lane_opponent(self, enemy_picks: list[str], target_role: str | None):
        target_role = self.normalize_role(target_role)

        if not target_role:
            return None, "unknown"

        enemy_roles = self.infer_team_roles(enemy_picks)
        info = enemy_roles.get(target_role)

        if not info:
            return None, "unknown"

        return info.get("champion"), info.get("confidence", "unknown")