import json
import time
from pathlib import Path
from typing import Optional

import requests

from config import BASE_DIR


ASSETS_DIR = BASE_DIR / "assets" / "champions"
DATA_DIR = BASE_DIR / "data"
CHAMPIONS_JSON = DATA_DIR / "champions.json"


def get_latest_ddragon_version() -> str:
    url = "https://ddragon.leagueoflegends.com/api/versions.json"

    resp = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    resp.raise_for_status()

    versions = resp.json()
    if not versions:
        raise RuntimeError("没有获取到 Data Dragon 版本列表")

    return versions[0]


def download_with_retry(
    url: str,
    save_path: Path,
    max_retries: int = 5,
    timeout: int = 30,
) -> bool:
    """
    下载文件，失败自动重试。
    已存在的文件会跳过。
    """
    if save_path.exists() and save_path.stat().st_size > 0:
        print(f"已存在，跳过：{save_path.name}")
        return True

    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers=headers,
            )
            resp.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(resp.content)

            print(f"下载成功：{save_path.name}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"下载失败 {save_path.name}，第 {attempt}/{max_retries} 次重试：{e}")

            if attempt < max_retries:
                time.sleep(2 * attempt)

    print(f"最终失败：{save_path.name}")
    return False


def download_champion_icons(language: str = "zh_CN") -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    version = get_latest_ddragon_version()
    print(f"Data Dragon 最新版本：{version}")

    champion_json_url = (
        f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{language}/champion.json"
    )

    resp = requests.get(
        champion_json_url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    resp.raise_for_status()

    champion_data = resp.json()["data"]

    champions_map = {}
    failed = []

    for champion_id, info in champion_data.items():
        image_file = info["image"]["full"]
        image_url = (
            f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{image_file}"
        )

        save_path = ASSETS_DIR / image_file

        print(f"\n准备下载：{info['name']} -> {save_path.name}")

        ok = download_with_retry(image_url, save_path)

        if not ok:
            failed.append(image_file)
            continue

        champions_map[Path(image_file).stem] = {
            "id": champion_id,
            "name": info["name"],
            "title": info.get("title", ""),
            "image": image_file,
        }

    with open(CHAMPIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(champions_map, f, ensure_ascii=False, indent=2)

    print("\n下载流程结束。")
    print(f"英雄头像目录：{ASSETS_DIR}")
    print(f"英雄数据文件：{CHAMPIONS_JSON}")
    print(f"成功数量：{len(champions_map)}")

    if failed:
        print("\n以下文件下载失败，可以重新运行脚本继续下载：")
        for item in failed:
            print(f"- {item}")
    else:
        print("全部英雄头像下载成功。")


if __name__ == "__main__":
    download_champion_icons()