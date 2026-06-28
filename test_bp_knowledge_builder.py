from bp_knowledge_builder import BPKnowledgeBuilder

builder = BPKnowledgeBuilder()

result = builder.build_bp_evidence(
    candidate_ids=["Malphite", "Poppy", "Ornn", "Fiora", "Jax"],
    ally_picks=["Jinx", "Lulu"],
    enemy_picks=["Aatrox", "LeeSin", "Ahri"],
    target_role="上单",
    lane_opponent="Aatrox",
)

for item in result["candidates"]:
    print("\n====================")
    print(item["champion"], "score =", item["evidence_score"])
    for e in item["evidence"]:
        print("-", e)