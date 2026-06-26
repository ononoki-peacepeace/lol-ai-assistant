import argparse
import time
from typing import List, Optional

from config import (
    CAPTURE_INTERVAL,
    BLUE_BAN_SLOTS,
    RED_BAN_SLOTS,
    BLUE_PICK_SLOTS,
    RED_PICK_SLOTS,
)
from riot_api import RiotAPIError
from player_analyzer import PlayerAnalyzer
from screen_capture import ScreenCapture
from champion_detector import ChampionDetector
from bp_state import BPState


def analyze_player_command(game_name: str, tag_line: str) -> None:
    """
    查询某个玩家最近 20 局常用英雄。
    """
    analyzer = PlayerAnalyzer()

    try:
        result = analyzer.analyze_player(game_name, tag_line)
    except RiotAPIError as e:
        print(f"查询失败：{e}")
        return

    print("\n玩家分析结果：")
    print(f"召唤师：{result['summoner']}")
    print(f"常见位置：{result['main_position']}")
    print(f"分析场数：{result['matches_analyzed']}")
    print("常用英雄：")

    for item in result["top_champions"]:
        print(f"- {item['champion']}: {item['count']} 场")


def detect_bp_once(
    capture: ScreenCapture,
    detector: ChampionDetector,
) -> tuple[
    List[Optional[str]],
    List[Optional[str]],
    List[Optional[str]],
    List[Optional[str]],
]:
    """
    截图一次并识别当前 Ban/Pick。
    """
    frame = capture.capture()

    blue_ban_images = [capture.crop(frame, slot) for slot in BLUE_BAN_SLOTS]
    red_ban_images = [capture.crop(frame, slot) for slot in RED_BAN_SLOTS]
    blue_pick_images = [capture.crop(frame, slot) for slot in BLUE_PICK_SLOTS]
    red_pick_images = [capture.crop(frame, slot) for slot in RED_PICK_SLOTS]

    blue_bans = detector.detect_slots(blue_ban_images)
    red_bans = detector.detect_slots(red_ban_images)
    blue_picks = detector.detect_slots(blue_pick_images)
    red_picks = detector.detect_slots(red_pick_images)

    return blue_bans, red_bans, blue_picks, red_picks


def infer_phase(
    blue_bans: List[Optional[str]],
    red_bans: List[Optional[str]],
    blue_picks: List[Optional[str]],
    red_picks: List[Optional[str]],
) -> str:
    """
    简单推断当前阶段。

    第一版：
    - 如果 Pick 槽位里有英雄，认为是 PICK 阶段
    - 否则如果 Ban 槽位里有英雄，认为是 BAN 阶段
    - 否则 UNKNOWN
    """
    pick_count = sum(1 for x in blue_picks + red_picks if x)
    ban_count = sum(1 for x in blue_bans + red_bans if x)

    if pick_count > 0:
        return "PICK"
    if ban_count > 0:
        return "BAN"
    return "UNKNOWN"


def watch_bp_command() -> None:
    """
    实时监听 BP 状态。
    """
    capture = ScreenCapture()
    detector = ChampionDetector()
    bp_state = BPState()

    print("开始监听 LOL BP 状态...")
    print("按 Ctrl + C 停止。")

    try:
        while True:
            blue_bans, red_bans, blue_picks, red_picks = detect_bp_once(
                capture,
                detector,
            )

            phase = infer_phase(
                blue_bans,
                red_bans,
                blue_picks,
                red_picks,
            )

            changed = bp_state.update(
                blue_bans=blue_bans,
                red_bans=red_bans,
                blue_picks=blue_picks,
                red_picks=red_picks,
                phase=phase,
            )

            if changed:
                bp_state.pretty_print()

            time.sleep(CAPTURE_INTERVAL)

    except KeyboardInterrupt:
        print("\n已停止监听。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LOL BP 实时辅助工具 MVP"
    )

    subparsers = parser.add_subparsers(dest="command")

    player_parser = subparsers.add_parser(
        "analyze-player",
        help="分析某个玩家最近 20 局常用英雄",
    )
    player_parser.add_argument("--game-name", required=True, help="Riot ID 的名称部分")
    player_parser.add_argument("--tag-line", required=True, help="Riot ID 的 tagLine 部分，例如 KR1")

    subparsers.add_parser(
        "watch-bp",
        help="实时截图并识别 Ban/Pick 状态",
    )

    args = parser.parse_args()

    if args.command == "analyze-player":
        analyze_player_command(args.game_name, args.tag_line)
    elif args.command == "watch-bp":
        watch_bp_command()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()