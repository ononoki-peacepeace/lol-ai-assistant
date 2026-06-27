from bp_analyzer import BPAnalyzer
from champion_recommender import ChampionRecommender
from ai_commentator import AICommentator


analyzer = BPAnalyzer()
recommender = ChampionRecommender()
ai = AICommentator()

ally_picks = ["Ashe", "LeeSin", "Orianna"]
enemy_picks = ["Kaisa", "Nautilus", "XinZhao"]
banned_champions = []

target_role = "上单"

analysis = analyzer.analyze(ally_picks, enemy_picks)

recommendations = recommender.recommend(
    triggered_rules=analysis["triggered_rules"],
    target_role=target_role,
    ally_picks=ally_picks,
    enemy_picks=enemy_picks,
    banned_champions=banned_champions,
    top_n=5,
)

print("===== 推荐英雄 =====")
for item in recommendations:
    print(
        f"{item['name']}({item['id']}) "
        f"分数:{item['score']} "
        f"命中标签:{item['matched_tags']} "
        f"全部标签:{item['all_tags']}"
    )

print("\n===== AI 解释 =====")
if recommendations:
    print(ai.explain_bp(analysis, recommendations, target_role=target_role))
else:
    print("暂无可推荐英雄。")