import os
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

from core import constants
from core.storage import load_json, save_json


@dataclass
class LeaderboardEntry:
    player_name: str
    difficulty: str
    score: int
    timestamp: float
    graph_count: int


class LeaderboardSystem:
    LEADERBOARD_FILE = "leaderboard.json"
    MAX_ENTRIES = constants.LEADERBOARD_MAX_ENTRIES

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(constants.DATA_DIR, self.LEADERBOARD_FILE)
        self.entries: List[LeaderboardEntry] = self.load()

    def load(self) -> List[LeaderboardEntry]:
        data = load_json(self.path, [])
        entries = []
        if isinstance(data, list):
            for row in data:
                try:
                    entry = LeaderboardEntry(
                        player_name=str(row["player_name"])[:constants.PLAYER_NAME_MAX_LEN],
                        difficulty=str(row["difficulty"]), score=int(row["score"]),
                        timestamp=float(row["timestamp"]), graph_count=int(row["graph_count"]))
                except (KeyError, TypeError, ValueError):
                    continue
                if entry.difficulty in constants.DIFFICULTY_CONFIG:
                    entries.append(entry)
        self._sort_and_prune(entries)
        return entries

    def save(self) -> bool:
        return save_json(self.path, [asdict(e) for e in self.entries])

    def _sort_and_prune(self, entries: List[LeaderboardEntry]):
        entries.sort(key=lambda e: (-e.score, e.timestamp))
        kept, per_difficulty = [], {}
        for e in entries:
            count = per_difficulty.get(e.difficulty, 0)
            if count < self.MAX_ENTRIES:
                kept.append(e)
                per_difficulty[e.difficulty] = count + 1
        entries[:] = kept

    def add_entry(self, player_name: str, difficulty: str, score: int,
                  graph_count: int) -> Optional[int]:
        entry = LeaderboardEntry(player_name=player_name, difficulty=difficulty, score=int(score),
                                 timestamp=time.time(), graph_count=int(graph_count))
        self.entries.append(entry)
        self._sort_and_prune(self.entries)
        self.save()
        ranked = [e for e in self.entries if e.difficulty == difficulty]
        for rank, e in enumerate(ranked, 1):
            if e is entry:
                return rank
        return None

    def get_top_by_difficulty(self, difficulty: str,
                              limit: int = constants.LEADERBOARD_TOP_N) -> List[LeaderboardEntry]:
        return [e for e in self.entries if e.difficulty == difficulty][:limit]
