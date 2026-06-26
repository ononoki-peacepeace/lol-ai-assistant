from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd

from config import MATCH_COUNT
from riot_api import RiotAPI, RiotAPIError


class PlayerAnalyzer:
    """
    分析玩家最近对局常用英雄。
    """

    def __init__(self, riot_api: Optional[RiotAPI] = None):
        self.riot_api = riot_api or RiotAPI()

    def analyze_player(
        self,
        game_name: str,
        tag_line: str,
        match_count: int = MATCH_COUNT,
    ) -> Dict[str, Any]:
        """
        输入 Riot ID，输出最近 match_count 局常用英雄和常见位置。
        """
        account = self.riot_api.get_account_by_riot_id(game_name, tag_line)
        puuid = account["puuid"]

        match_ids = self.riot_api.get_match_ids_by_puuid(puuid, count=match_count)

        rows: List[Dict[str, Any]] = []

        for match_id in match_ids:
            try:
                detail = self.riot_api.get_match_detail(match_id)
                participant = self._find_participant(detail, puuid)

                if participant:
                    rows.append({
                        "match_id": match_id,
                        "champion": participant.get("championName", "UNKNOWN"),
                        "team_position": participant.get("teamPosition", "UNKNOWN"),
                        "win": participant.get("win", False),
                        "kills": participant.get("kills", 0),
                        "deaths": participant.get("deaths", 0),
                        "assists": participant.get("assists", 0),
                    })
            except RiotAPIError as e:
                print(f"跳过比赛 {match_id}: {e}")

        if not rows:
            return {
                "summoner": f"{game_name}#{tag_line}",
                "main_position": "UNKNOWN",
                "top_champions": [],
                "matches_analyzed": 0,
            }

        df = pd.DataFrame(rows)

        champion_counts = Counter(df["champion"])
        position_counts = Counter(df["team_position"])

        top_champions = [
            {
                "champion": champion,
                "count": count,
            }
            for champion, count in champion_counts.most_common(3)
        ]

        main_position = position_counts.most_common(1)[0][0]

        return {
            "summoner": f"{game_name}#{tag_line}",
            "main_position": main_position,
            "top_champions": top_champions,
            "matches_analyzed": len(rows),
        }

    @staticmethod
    def _find_participant(match_detail: Dict[str, Any], puuid: str) -> Optional[Dict[str, Any]]:
        participants = match_detail.get("info", {}).get("participants", [])
        for participant in participants:
            if participant.get("puuid") == puuid:
                return participant
        return None