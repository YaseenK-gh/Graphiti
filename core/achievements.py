"""Achievement badges and per-difficulty streaks (persisted to JSON)."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core import constants
from core.storage import load_json, save_json

# badge id → (display name, how to earn it)
BADGE_INFO: Dict[str, Tuple[str, str]] = {
    "perfect_easy": ("PERFECT NOVICE", "Complete EASY with 0 resets and 0 forfeits"),
    "perfect_medium": ("PERFECT ARCHITECT", "Complete MEDIUM with 0 resets and 0 forfeits"),
    "perfect_hard": ("PERFECT CRYPTOGRAPHER", "Complete HARD with 0 resets and 0 forfeits"),
    "speedrun_easy": ("EASY SPEEDRUN", "Hit the max time bonus on every EASY graph"),
    "speedrun_medium": ("MEDIUM SPEEDRUN", "Hit the max time bonus on every MEDIUM graph"),
    "speedrun_hard": ("HARD SPEEDRUN", "Hit the max time bonus on every HARD graph"),
    "hint_master": ("HINT MASTER", "Complete any difficulty without buying a hint"),
    "colorblind": ("COLORBLIND", f"Solve {constants.COLORBLIND_SOLVES} graphs (any mode)"),
}


def badge_name(badge: str) -> str:
    return BADGE_INFO.get(badge, (badge.upper(), ""))[0]


@dataclass
class AchievementSystem:
    """Track player achievements and streaks.

    A streak counts consecutive clean (0-reset, 0-forfeit) clears of a
    difficulty; any reset or forfeit during a run breaks it.
    """

    easy_streak: int = 0
    medium_streak: int = 0
    hard_streak: int = 0
    badges_earned: Set[str] = field(default_factory=set)
    graphs_solved: int = 0
    save_path: Optional[str] = field(default=None, repr=False, compare=False)

    FILE_NAME = "achievements.json"
    BADGE_PERFECT_EASY = "perfect_easy"
    BADGE_PERFECT_MEDIUM = "perfect_medium"
    BADGE_PERFECT_HARD = "perfect_hard"
    BADGE_SPEEDRUN_EASY = "speedrun_easy"
    BADGE_SPEEDRUN_MEDIUM = "speedrun_medium"
    BADGE_SPEEDRUN_HARD = "speedrun_hard"
    BADGE_HINT_MASTER = "hint_master"
    BADGE_COLORBLIND = "colorblind"

    # ─── Persistence ──────────────────────────────────────────────────────────

    @classmethod
    def default_path(cls) -> str:
        return os.path.join(constants.DATA_DIR, cls.FILE_NAME)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AchievementSystem":
        path = path or cls.default_path()
        data = load_json(path, {})
        system = cls(save_path=path)
        if isinstance(data, dict):
            for name in ("easy_streak", "medium_streak", "hard_streak", "graphs_solved"):
                value = data.get(name, 0)
                if isinstance(value, int) and value >= 0:
                    setattr(system, name, value)
            badges = data.get("badges_earned", [])
            if isinstance(badges, list):
                system.badges_earned = {b for b in badges if b in BADGE_INFO}
        return system

    def save(self) -> bool:
        if not self.save_path:
            return False
        return save_json(self.save_path, {
            "easy_streak": self.easy_streak,
            "medium_streak": self.medium_streak,
            "hard_streak": self.hard_streak,
            "graphs_solved": self.graphs_solved,
            "badges_earned": sorted(self.badges_earned),
        })

    # ─── Rules ────────────────────────────────────────────────────────────────

    def _award(self, badge: str, new: List[str]):
        if badge not in self.badges_earned:
            self.badges_earned.add(badge)
            new.append(badge)

    def get_streak(self, difficulty: str) -> int:
        return getattr(self, f"{difficulty.lower()}_streak", 0)

    def _set_streak(self, difficulty: str, value: int):
        setattr(self, f"{difficulty.lower()}_streak", value)

    def record_graph_solved(self) -> List[str]:
        """Count a solved graph (either mode). Returns newly earned badges."""
        new: List[str] = []
        self.graphs_solved += 1
        if self.graphs_solved >= constants.COLORBLIND_SOLVES:
            self._award(self.BADGE_COLORBLIND, new)
        self.save()
        return new

    def on_difficulty_completed(self, difficulty: str, resets: int, all_max_time: bool,
                                hints_used: int, forfeits: int = 0) -> List[str]:
        """Update streaks and badges after a difficulty. Returns newly earned badges."""
        new: List[str] = []
        key = difficulty.lower()
        if resets == 0 and forfeits == 0:
            self._set_streak(difficulty, self.get_streak(difficulty) + 1)
            self._award(f"perfect_{key}", new)
        else:
            self._set_streak(difficulty, 0)
        if all_max_time:
            self._award(f"speedrun_{key}", new)
        if hints_used == 0:
            self._award(self.BADGE_HINT_MASTER, new)
        self.save()
        return new
