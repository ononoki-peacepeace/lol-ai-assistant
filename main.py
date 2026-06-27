import argparse
import time
from typing import List, Optional

from config import (
    CAPTURE_INTERVAL,
    TEMPLATE_SIZE,
    ROLE_MAP,
    load_layout,
)

from screen_capture import ScreenCapture
from champion_detector import ChampionDetector
from bp_state import BPState

from bp_analyzer import BPAnalyzer
from champion_recommender import ChampionRecommender
from ai_commentator import AICommentator

def analyze_player_command(game_name: str, tag_line: str) -> None:
    """
    查询某个玩家最近 20 局常用英雄。
    只有真正执行 analyze-player 时，才导入 Riot API 相关模块。
    """
    from riot_api import RiotAPIError
    from player_analyzer import PlayerAnalyzer

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

def crop_slot(frame, slot, size: int = TEMPLATE_SIZE):
    """
    从截图中裁出一个槽位小图。

    支持三种格式：
    1. [x, y]             以中心点裁 size x size
    2. [x1, y1, x2, y2]   直接按矩形裁剪
    3. [x, y, w, h]       按左上角 + 宽高裁剪
    """
    h, w = frame.shape[:2]

    if isinstance(slot, dict):
        if "center" in slot:
            x, y = slot["center"]
            slot = [x, y]
        elif all(k in slot for k in ["x", "y"]):
            slot = [slot["x"], slot["y"]]
        elif all(k in slot for k in ["left", "top", "width", "height"]):
            left = int(slot["left"])
            top = int(slot["top"])
            right = int(left + slot["width"])
            bottom = int(top + slot["height"])

            left = max(0, left)
            top = max(0, top)
            right = min(w, right)
            bottom = min(h, bottom)

            return frame[top:bottom, left:right]
        else:
            raise ValueError(f"不支持的 slot 字典格式: {slot}")

    if len(slot) == 2:
        x, y = slot
        x = int(x)
        y = int(y)

        half = size // 2

        left = max(0, x - half)
        top = max(0, y - half)
        right = min(w, x + half)
        bottom = min(h, y + half)

        return frame[top:bottom, left:right]

    if len(slot) == 4:
        a, b, c, d = map(int, slot)

        # 如果 c/d 看起来像右下角，就按 x1,y1,x2,y2 处理
        if c > a and d > b:
            left, top, right, bottom = a, b, c, d
        else:
            # 否则按 x,y,w,h 处理
            left, top, right, bottom = a, b, a + c, b + d

        left = max(0, left)
        top = max(0, top)
        right = min(w, right)
        bottom = min(h, bottom)

        return frame[top:bottom, left:right]

    raise ValueError(f"不支持的 slot 格式: {slot}")

def scale_slot(slot, layout: dict, frame):
    """
    把 layout 里的基准坐标缩放到当前截图尺寸。
    支持：
    - client_pixel: 基于 base_width/base_height 的像素坐标
    - client_ratio: 0~1 的比例坐标
    """
    frame_h, frame_w = frame.shape[:2]

    coord_type = layout.get("coord_type", "client_pixel")
    base_w = layout.get("base_width", frame_w)
    base_h = layout.get("base_height", frame_h)

    if isinstance(slot, dict):
        if "center" in slot:
            x, y = slot["center"]
            scaled_center = scale_slot([x, y], layout, frame)
            return {"center": scaled_center}

        if all(k in slot for k in ["left", "top", "width", "height"]):
            left = slot["left"]
            top = slot["top"]
            width = slot["width"]
            height = slot["height"]

            if coord_type == "client_ratio":
                return {
                    "left": int(left * frame_w),
                    "top": int(top * frame_h),
                    "width": int(width * frame_w),
                    "height": int(height * frame_h),
                }

            sx = frame_w / base_w
            sy = frame_h / base_h

            return {
                "left": int(left * sx),
                "top": int(top * sy),
                "width": int(width * sx),
                "height": int(height * sy),
            }

        return slot

    if coord_type == "client_ratio":
        if len(slot) == 2:
            x, y = slot
            return [int(x * frame_w), int(y * frame_h)]

        if len(slot) == 4:
            x1, y1, x2, y2 = slot
            return [
                int(x1 * frame_w),
                int(y1 * frame_h),
                int(x2 * frame_w),
                int(y2 * frame_h),
            ]

    sx = frame_w / base_w
    sy = frame_h / base_h

    if len(slot) == 2:
        x, y = slot
        return [int(x * sx), int(y * sy)]

    if len(slot) == 4:
        a, b, c, d = slot
        return [
            int(a * sx),
            int(b * sy),
            int(c * sx),
            int(d * sy),
        ]

    return slot

def detect_slot_group(
    frame,
    detector: ChampionDetector,
    slot_centers: list[list[int]],
    layout: dict,
) -> List[Optional[str]]:
    """
    识别一组槽位。
    会先把 layout 坐标按当前截图尺寸缩放。
    """
    if not slot_centers:
        return []

    scaled_slots = [
        scale_slot(slot, layout, frame)
        for slot in slot_centers
    ]

    slot_images = [
        crop_slot(frame, slot)
        for slot in scaled_slots
    ]

    return detector.detect_slots(slot_images)


def detect_bp_once(
    capture: ScreenCapture,
    detector: ChampionDetector,
    layout: dict,
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
    
    blue_ban_slots = layout.get("blue_bans", [])
    red_ban_slots = layout.get("red_bans", [])
    blue_pick_slots = layout.get("blue_picks", [])
    red_pick_slots = layout.get("red_picks", [])

    blue_bans = detect_slot_group(frame, detector, blue_ban_slots, layout)
    red_bans = detect_slot_group(frame, detector, red_ban_slots, layout)
    blue_picks = detect_slot_group(frame, detector, blue_pick_slots, layout)
    red_picks = detect_slot_group(frame, detector, red_pick_slots, layout)

    return blue_bans, red_bans, blue_picks, red_picks


def infer_phase(
    blue_bans: List[Optional[str]],
    red_bans: List[Optional[str]],
    blue_picks: List[Optional[str]],
    red_picks: List[Optional[str]],
) -> str:
    """
    简单推断当前阶段。
    """
    pick_count = sum(1 for x in blue_picks + red_picks if x)
    ban_count = sum(1 for x in blue_bans + red_bans if x)

    if pick_count > 0:
        return "PICK"
    if ban_count > 0:
        return "BAN"
    return "UNKNOWN"


def normalize_role(role: str | None) -> str | None:
    """
    把 top / mid / adc 等转换成中文位置。
    """
    if not role:
        return None

    return ROLE_MAP.get(role.lower(), role)


def choose_ally_enemy(
    side: str,
    blue_picks: List[Optional[str]],
    red_picks: List[Optional[str]],
) -> tuple[list[str], list[str]]:
    """
    根据自己是蓝方还是红方，区分己方和敌方。
    """
    blue = [x for x in blue_picks if x]
    red = [x for x in red_picks if x]

    if side == "red":
        return red, blue

    return blue, red


def flatten_existing(*groups: List[Optional[str]]) -> list[str]:
    """
    合并已选 / 已 ban 英雄，过滤 None。
    """
    result = []

    for group in groups:
        for item in group:
            if item:
                result.append(item)

    return result


def print_recommendations(recommendations: list[dict]) -> None:
    """
    打印推荐英雄和评分理由。
    """
    print("\n===== 推荐英雄 =====")

    if not recommendations:
        print("暂无推荐。")
        return

    for item in recommendations:
        print(
            f"{item['name']}({item['id']}) "
            f"分数:{item['score']} "
            f"命中标签:{item.get('matched_tags', [])}"
        )

        for reason in item.get("score_reasons", []):
            print(f"  - {reason}")


def run_bp_recommendation(
    side: str,
    role: str | None,
    use_ai: bool,
    blue_bans: List[Optional[str]],
    red_bans: List[Optional[str]],
    blue_picks: List[Optional[str]],
    red_picks: List[Optional[str]],
) -> None:
    """
    根据当前 BP 状态进行推荐。
    """
    target_role = normalize_role(role)

    ally_picks, enemy_picks = choose_ally_enemy(
        side=side,
        blue_picks=blue_picks,
        red_picks=red_picks,
    )

    banned_champions = flatten_existing(blue_bans, red_bans)

    analyzer = BPAnalyzer()
    recommender = ChampionRecommender()

    analysis = analyzer.analyze(
        ally_picks=ally_picks,
        enemy_picks=enemy_picks,
    )

    recommendations = recommender.recommend(
        triggered_rules=analysis.get("triggered_rules", []),
        target_role=target_role,
        ally_picks=ally_picks,
        enemy_picks=enemy_picks,
        banned_champions=banned_champions,
        top_n=5,
    )

    print_recommendations(recommendations)

    if use_ai and recommendations:
        print("\n===== AI 解释 =====")
        ai = AICommentator()
        print(
            ai.explain_bp(
                analysis=analysis,
                recommendations=recommendations,
                target_role=target_role,
            )
        )


def watch_bp_command(side: str, role: str | None, use_ai: bool) -> None:
    """
    实时监听 BP 状态。
    """
    layout = load_layout()

    if not layout:
        print("没有读取到布局文件。请确认 data/default_layout_1280x720.json 是否存在。")
        return

    capture = ScreenCapture()
    detector = ChampionDetector()
    bp_state = BPState()

    print("开始监听 LOL BP 状态...")
    print(f"使用阵营: {side}")
    print(f"目标位置: {normalize_role(role) or '未指定'}")
    print(f"AI 解释: {'开启' if use_ai else '关闭'}")
    print("按 Ctrl + C 停止。")

    try:
        while True:
            blue_bans, red_bans, blue_picks, red_picks = detect_bp_once(
                capture=capture,
                detector=detector,
                layout=layout,
            )

            phase = infer_phase(
                blue_bans=blue_bans,
                red_bans=red_bans,
                blue_picks=blue_picks,
                red_picks=red_picks,
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

                if phase == "PICK":
                    run_bp_recommendation(
                        side=side,
                        role=role,
                        use_ai=use_ai,
                        blue_bans=blue_bans,
                        red_bans=red_bans,
                        blue_picks=blue_picks,
                        red_picks=red_picks,
                    )

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

    watch_parser = subparsers.add_parser(
        "watch-bp",
        help="实时截图并识别 Ban/Pick 状态",
    )
    watch_parser.add_argument(
        "--side",
        choices=["blue", "red"],
        default="blue",
        help="你所在的阵营，默认 blue",
    )
    watch_parser.add_argument(
        "--role",
        default=None,
        help="目标位置，例如 top / jungle / mid / adc / support",
    )
    watch_parser.add_argument(
        "--ai",
        action="store_true",
        help="开启 AI BP 解释",
    )

    args = parser.parse_args()

    if args.command == "analyze-player":
        analyze_player_command(args.game_name, args.tag_line)
    elif args.command == "watch-bp":
        watch_bp_command(
            side=args.side,
            role=args.role,
            use_ai=args.ai,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()