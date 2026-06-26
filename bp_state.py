from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import copy


@dataclass
class BPState:
    """
    保存当前 BP 状态。
    """

    blue_bans: List[Optional[str]] = field(default_factory=list)
    red_bans: List[Optional[str]] = field(default_factory=list)
    blue_picks: List[Optional[str]] = field(default_factory=list)
    red_picks: List[Optional[str]] = field(default_factory=list)
    phase: str = "UNKNOWN"

    last_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "blue_bans": self.blue_bans,
            "red_bans": self.red_bans,
            "blue_picks": self.blue_picks,
            "red_picks": self.red_picks,
        }

    def update(
        self,
        blue_bans: List[Optional[str]],
        red_bans: List[Optional[str]],
        blue_picks: List[Optional[str]],
        red_picks: List[Optional[str]],
        phase: str,
    ) -> bool:
        """
        更新状态。

        返回：
        True  = 状态发生变化
        False = 状态没有变化
        """
        self.blue_bans = blue_bans
        self.red_bans = red_bans
        self.blue_picks = blue_picks
        self.red_picks = red_picks
        self.phase = phase

        current = self.to_dict()

        if current != self.last_state:
            self.last_state = copy.deepcopy(current)
            return True

        return False

    def pretty_print(self) -> None:
        print("\n" + "=" * 50)
        print(f"当前阶段：{self.phase}")
        print(f"蓝方 Ban：{self._format_list(self.blue_bans)}")
        print(f"红方 Ban：{self._format_list(self.red_bans)}")
        print(f"蓝方 Pick：{self._format_list(self.blue_picks)}")
        print(f"红方 Pick：{self._format_list(self.red_picks)}")
        print("=" * 50 + "\n")

    @staticmethod
    def _format_list(items: List[Optional[str]]) -> str:
        visible = [item for item in items if item]
        if not visible:
            return "暂无"
        return ", ".join(visible)