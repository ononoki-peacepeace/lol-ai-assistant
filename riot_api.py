import time
from typing import Any, Dict, List, Optional

import requests

from config import RIOT_API_KEY, REGIONAL_ROUTE, PLATFORM_ROUTE


class RiotAPIError(Exception):
    pass


class RiotAPI:
    """
    Riot 官方 API 简单封装。

    主要功能：
    1. 根据 Riot ID 获取 puuid
    2. 根据 puuid 获取最近比赛 ID
    3. 根据 match_id 获取比赛详情
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        regional_route: str = REGIONAL_ROUTE,
        platform_route: str = PLATFORM_ROUTE,
        timeout: int = 10,
    ):
        self.api_key = api_key or RIOT_API_KEY
        self.regional_route = regional_route
        self.platform_route = platform_route
        self.timeout = timeout

        if not self.api_key:
            raise RiotAPIError("RIOT_API_KEY 未配置，请在 .env 中设置 RIOT_API_KEY。")

        self.headers = {
            "X-Riot-Token": self.api_key
        }

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any] | List[Any]:
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise RiotAPIError(f"请求 Riot API 失败: {e}") from e

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "2"))
            print(f"触发 Riot API 限流，等待 {retry_after} 秒后重试...")
            time.sleep(retry_after)
            return self._request(url, params)

        if response.status_code >= 400:
            raise RiotAPIError(
                f"Riot API 返回错误: {response.status_code}, {response.text}"
            )

        return response.json()

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> Dict[str, Any]:
        """
        根据 Riot ID 获取账号信息。

        示例：
        game_name = "Hide on bush"
        tag_line = "KR1"
        """
        url = (
            f"https://{self.regional_route}.api.riotgames.com"
            f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )
        data = self._request(url)
        if not isinstance(data, dict):
            raise RiotAPIError("获取 account 信息失败，返回不是 dict。")
        return data

    def get_match_ids_by_puuid(self, puuid: str, count: int = 20) -> List[str]:
        """
        根据 puuid 获取最近比赛 ID。
        """
        url = (
            f"https://{self.regional_route}.api.riotgames.com"
            f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
        )
        params = {
            "start": 0,
            "count": count,
        }
        data = self._request(url, params=params)
        if not isinstance(data, list):
            raise RiotAPIError("获取 match ids 失败，返回不是 list。")
        return data

    def get_match_detail(self, match_id: str) -> Dict[str, Any]:
        """
        获取某一局比赛详情。
        """
        url = (
            f"https://{self.regional_route}.api.riotgames.com"
            f"/lol/match/v5/matches/{match_id}"
        )
        data = self._request(url)
        if not isinstance(data, dict):
            raise RiotAPIError("获取 match detail 失败，返回不是 dict。")
        return data