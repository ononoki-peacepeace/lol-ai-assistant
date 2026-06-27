from bp_analyzer import BPAnalyzer
from champion_recommender import ChampionRecommender


test_cases = [
    {
        "name": "发条 + 石头人配合，同时敌方有亚索和塞拉斯",
        "ally": ["Orianna", "Ashe", "LeeSin"],
        "enemy": ["Yasuo", "Sylas", "Blitzcrank"],
        "role": "上单"
    },
    {
        "name": "辅助位面对机器人，测试莫甘娜 counter",
        "ally": ["Jinx", "Orianna", "LeeSin"],
        "enemy": ["Blitzcrank", "Zed", "Kaisa"],
        "role": "辅助"
    },
    {
        "name": "上单位面对青钢影，测试波比 counter",
        "ally": ["Jinx", "Lux", "Viego"],
        "enemy": ["Camille", "Ahri", "Nautilus"],
        "role": "上单"
    },
    {
        "name": "中单位面对劫，测试丽桑卓 counter",
        "ally": ["Jinx", "Lulu", "Sejuani"],
        "enemy": ["Zed", "Kaisa", "Leona"],
        "role": "中单"
    },
    {
        "name": "下路面对多前排，测试薇恩打坦",
        "ally": ["Ahri", "LeeSin", "Lux"],
        "enemy": ["Ornn", "Sion", "Nautilus"],
        "role": "下路"
    }
]


def main():
    analyzer = BPAnalyzer()
    recommender = ChampionRecommender()

    for case in test_cases:
        print("\n" + "=" * 70)
        print(f"测试用例：{case['name']}")
        print(f"己方：{case['ally']}")
        print(f"敌方：{case['enemy']}")
        print(f"目标位置：{case['role']}")

        analysis = analyzer.analyze(
            ally_picks=case["ally"],
            enemy_picks=case["enemy"],
        )

        print("\n触发规则：")
        for rule in analysis.get("triggered_rules", []):
            print(f"- [{rule.get('priority')}] {rule.get('name')}")
            print(f"  {rule.get('recommend', {}).get('short')}")

        recommendations = recommender.recommend(
            triggered_rules=analysis.get("triggered_rules", []),
            target_role=case["role"],
            ally_picks=case["ally"],
            enemy_picks=case["enemy"],
            banned_champions=[],
            top_n=5,
        )

        print("\n推荐英雄：")
        for item in recommendations:
            print(
                f"- {item['name']}({item['id']}) "
                f"分数:{item['score']} "
                f"命中:{item.get('matched_tags', [])}"
            )

            for reason in item.get("score_reasons", []):
                print(f"  - {reason}")


if __name__ == "__main__":
    main()