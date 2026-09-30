"""Central game state: the Graph model, screen/mode enums and run bookkeeping.

The UI reads and mutates this object; the rules (timer, resets, scoring
bookkeeping) live here so they can be unit tested without Qt.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from core.achievements import AchievementSystem
from core.constants import DIFFICULTY_CONFIG, GRAPH_CONSTRAINTS
from core.hint_system import HintSystem
from core.leaderboard import LeaderboardSystem
from core.scoring import ScoringSystem
from core.validation import validate_player_name


class GameMode(Enum):
    STANDARD = "standard"
    FREE = "free"


class GameScreen(Enum):
    MENU = "menu"
    MODE_SELECT = "mode_select"
    DIFFICULTY_SELECT = "difficulty_select"
    FREE_GRAPH_SELECT = "free_graph_select"
    PRE_GAME = "pre_game"
    PLAYING = "playing"
    POST_LEVEL = "post_level"
    POST_DIFFICULTY = "post_difficulty"
    FREE_COMPLETE = "free_complete"


@dataclass
class Graph:
    """Represents a graph with vertices, edges, and chromatic number."""
    type: str
    n: int
    vertices: List[int]
    edges: List[Tuple[int, int]]
    chromatic_number: int
    layout: Dict[int, Tuple[float, float]] = field(default_factory=dict)  # {vertex_id: (x, y)}


@dataclass
class LevelResult:
    """Outcome of one solved (or forfeited) graph."""
    graph_type: str
    n: int
    time_seconds: float
    colors_used: int
    chromatic_number: int
    base: int = 0
    time_bonus: int = 0
    vertex_bonus: int = 0
    optimality_bonus: int = 0
    score: int = 0
    max_time_bonus: bool = False
    hints_used: int = 0
    forfeited: bool = False


@dataclass
class DifficultyResult:
    """Outcome of a completed difficulty run."""
    difficulty: str
    provisional_score: int
    banked_score: int
    all_max_time: bool
    resets: int
    hints_used: int
    forfeits: int
    graph_count: int
    graphs_completed: int
    new_badges: List[str] = field(default_factory=list)
    streak: int = 0
    leaderboard_rank: Optional[int] = None
    submitted: bool = False


@dataclass
class GameState:
    """Central game state manager."""

    # Current screen and mode
    current_screen: GameScreen = GameScreen.MENU
    game_mode: GameMode = GameMode.STANDARD

    # Difficulty & graph queue (STANDARD mode). The queue holds graph types;
    # the player picks n for each one on the PRE_GAME screen.
    difficulty: Optional[str] = None
    graph_queue: List[str] = field(default_factory=list)
    current_graph_index: int = 0
    current_graph: Optional[Graph] = None

    # Free mode selection
    selected_graph_type: Optional[str] = None
    selected_n: Optional[int] = None

    # Coloring state (the canvas shares this dict)
    coloring: Dict[int, Optional[int]] = field(default_factory=dict)
    active_color: int = 0
    conflicts: Set[str] = field(default_factory=set)

    # Timer: elapsed_ms accumulates finished segments; timer_start marks the running one.
    timer_start: Optional[float] = None
    timer_running: bool = False
    timer_elapsed_ms: int = 0

    # Scoring (STANDARD mode only)
    level_scores: List[int] = field(default_factory=list)
    resets: int = 0
    provisional_score: int = 0
    max_time_bonus_hits: int = 0
    total_banked: int = 0

    forfeits: int = 0
    level_results: List[LevelResult] = field(default_factory=list)

    # Last n played per graph type in this run; each later level of a type needs a bigger n.
    n_history: Dict[str, int] = field(default_factory=dict)

    # Hint tracking. hints_used is per level (reset on level reset, costs never refunded);
    # difficulty_hints_used counts the whole run.
    hints_used: int = 0
    hints_available: List[Tuple[int, int]] = field(default_factory=list)  # (vertex_id, color) given
    difficulty_hints_used: int = 0
    hint_last_click_ms: Optional[float] = None

    # Achievements & leaderboard (persisted under constants.DATA_DIR). Only these
    # survive a restart — a run in progress is never saved.
    achievement_system: AchievementSystem = field(default_factory=AchievementSystem.load)
    leaderboard_system: LeaderboardSystem = field(default_factory=LeaderboardSystem)
    pending_badges: List[str] = field(default_factory=list)  # Earned but not yet shown.

    # Transient data
    last_level_score: Optional[int] = None
    last_level_result: Optional[LevelResult] = None
    last_difficulty_result: Optional[DifficultyResult] = None

    # ─── Setup ────────────────────────────────────────────────────────────────

    def start_difficulty(self, difficulty: str, queue: List[str]):
        self.game_mode = GameMode.STANDARD
        self.difficulty = difficulty
        self.reset_for_new_difficulty()
        self.graph_queue = list(queue)
        self.current_graph_index = 0
        self.current_graph = None

    def start_free_mode(self):
        self.game_mode = GameMode.FREE
        self.difficulty = None
        self.current_graph = None

    def reset_for_new_difficulty(self):
        """Reset scoring state for a new difficulty."""
        self.level_scores = []
        self.level_results = []
        self.resets = 0
        self.forfeits = 0
        self.provisional_score = 0
        self.max_time_bonus_hits = 0
        self.difficulty_hints_used = 0
        self.n_history = {}
        self.last_level_score = None
        self.last_level_result = None
        self.last_difficulty_result = None

    def reset_for_new_graph(self):
        """Reset coloring state for a new graph attempt."""
        self.coloring = {v: None for v in range(self.current_graph.n)}
        self.conflicts = set()
        self.active_color = 0
        self.hints_used = 0
        self.hints_available = []
        self.hint_last_click_ms = None
        self.start_timer()

    def abandon_run(self):
        """Quit mid-difficulty. Nothing is saved: the difficulty restarts from graph 1."""
        self.stop_timer()
        self.current_graph = None
        self.graph_queue = []
        self.current_graph_index = 0
        self.reset_for_new_difficulty()

    def is_standard(self) -> bool:
        return self.game_mode == GameMode.STANDARD

    def current_graph_type(self) -> Optional[str]:
        if 0 <= self.current_graph_index < len(self.graph_queue):
            return self.graph_queue[self.current_graph_index]
        return None

    def has_next_graph(self) -> bool:
        return self.current_graph_index + 1 < len(self.graph_queue)

    def advance_to_next_graph(self):
        self.current_graph_index += 1
        self.current_graph = None

    # ─── Increasing n per graph type (STANDARD) ───────────────────────────────

    def previous_n_for(self, graph_type: str) -> Optional[int]:
        return self.n_history.get(graph_type) if self.is_standard() else None

    def min_n_for(self, graph_type: str) -> int:
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        prev = self.previous_n_for(graph_type)
        return lo if prev is None else min(prev + 1, hi)

    def locked_n_for(self, graph_type: str) -> Optional[int]:
        """The max n once a type has been played at its max, else None."""
        hi = GRAPH_CONSTRAINTS[graph_type][1]
        prev = self.previous_n_for(graph_type)
        return hi if prev is not None and prev >= hi else None

    def begin_graph(self, graph: Graph):
        """Make `graph` current; in STANDARD mode its n becomes the bar for the next level of its type."""
        self.current_graph = graph
        if self.is_standard():
            self.n_history[graph.type] = graph.n

    # ─── Timer ────────────────────────────────────────────────────────────────

    def start_timer(self):
        """Start the game timer from zero."""
        self.timer_elapsed_ms = 0
        self.timer_start = time.monotonic()
        self.timer_running = True

    def pause_timer(self):
        if self.timer_running and self.timer_start is not None:
            self.timer_elapsed_ms += int((time.monotonic() - self.timer_start) * 1000)
            self.timer_running = False

    def resume_timer(self):
        if not self.timer_running:
            self.timer_start = time.monotonic()
            self.timer_running = True

    def stop_timer(self):
        """Stop the game timer; timer_elapsed_ms holds the final time."""
        self.pause_timer()

    def get_elapsed_seconds(self) -> float:
        """Current elapsed time in seconds (live while running)."""
        ms = self.timer_elapsed_ms
        if self.timer_running and self.timer_start is not None:
            ms += (time.monotonic() - self.timer_start) * 1000
        return ms / 1000.0

    # ─── Hints ────────────────────────────────────────────────────────────────

    def hint_cost(self) -> int:
        """Points per hint: difficulty-scaled in STANDARD, free in FREE mode."""
        return HintSystem.get_hint_cost(self.difficulty) if self.is_standard() else 0

    def hint_cooldown_remaining_ms(self, now_ms: Optional[float] = None) -> float:
        if self.hint_last_click_ms is None:
            return 0.0
        now_ms = time.monotonic() * 1000 if now_ms is None else now_ms
        return max(0.0, HintSystem.COOLDOWN_MS - (now_ms - self.hint_last_click_ms))

    def hint_block_reason(self, now_ms: Optional[float] = None) -> Optional[str]:
        """Why a hint can't be bought right now, or None if it can."""
        if self.hints_used >= HintSystem.MAX_HINTS_PER_LEVEL:
            return "No hints left for this level."
        remaining = self.hint_cooldown_remaining_ms(now_ms)
        if remaining > 0:
            return f"Hint available in {remaining / 1000:.1f}s"
        if self.is_standard() and self.provisional_score < self.hint_cost():
            return f"Not enough points (need {self.hint_cost():,})."
        return None

    def buy_hint(self, now_ms: Optional[float] = None) -> Tuple[Optional[Tuple[int, int]], Optional[str]]:
        """Purchase a hint. Returns ((vertex_id, color), None) or (None, reason)."""
        reason = self.hint_block_reason(now_ms)
        if reason:
            return None, reason
        hint = HintSystem.get_hint_for_vertex(self.current_graph, self.coloring)
        if hint is None:
            return None, "Nothing left to hint."
        if self.is_standard():
            self.provisional_score, _ = HintSystem.apply_hint_cost(self.provisional_score,
                                                                   self.difficulty)
        self.hints_used += 1
        self.difficulty_hints_used += 1
        self.hint_last_click_ms = time.monotonic() * 1000 if now_ms is None else now_ms
        self.hints_available.append(hint)
        return hint, None

    # ─── Resets ───────────────────────────────────────────────────────────────

    def apply_level_reset(self) -> int:
        """Restart the current graph. STANDARD mode loses 30% of the provisional score.

        Clears the coloring in place (the canvas shares the dict) and restarts the
        timer. Returns the number of points lost.
        """
        lost = 0
        if self.is_standard() and self.difficulty:
            new_score = ScoringSystem.apply_reset_penalty(self.provisional_score, self.difficulty)
            lost = self.provisional_score - new_score
            self.provisional_score = new_score
            self.resets += 1
        self.hints_used = 0  # Hint count is per attempt; the points spent are not refunded.
        self.hints_available = []
        for v in self.coloring:
            self.coloring[v] = None
        self.conflicts.clear()
        self.start_timer()
        return lost

    # ─── Completion ───────────────────────────────────────────────────────────

    def record_level_completion(self, colors_used: int, forfeited: bool = False) -> LevelResult:
        """Score the current graph and fold it into the run. Forfeits score 0."""
        self.stop_timer()
        graph = self.current_graph
        time_seconds = self.timer_elapsed_ms / 1000.0
        result = LevelResult(graph_type=graph.type, n=graph.n, time_seconds=time_seconds,
                             colors_used=colors_used, chromatic_number=graph.chromatic_number,
                             hints_used=self.hints_used, forfeited=forfeited)

        if self.is_standard() and self.difficulty:
            if not forfeited:
                breakdown = ScoringSystem.score_breakdown(self.difficulty, time_seconds, graph.n,
                                                          colors_used, graph.chromatic_number)
                result.base = breakdown['base']
                result.time_bonus = breakdown['time_bonus']
                result.vertex_bonus = breakdown['vertex_bonus']
                result.optimality_bonus = breakdown['optimality_bonus']
                result.score = breakdown['total']
                result.max_time_bonus = ScoringSystem.check_max_time_bonus(time_seconds,
                                                                           self.difficulty)
            else:
                self.forfeits += 1
            self.level_results.append(result)
            self.level_scores.append(result.score)
            self.provisional_score += result.score
            if result.max_time_bonus:
                self.max_time_bonus_hits += 1
            self.last_level_score = result.score

        if not forfeited:
            self.pending_badges.extend(self.achievement_system.record_graph_solved())
        self.last_level_result = result
        return result

    def take_pending_badges(self) -> List[str]:
        badges, self.pending_badges = self.pending_badges, []
        return badges

    def finalize_difficulty(self) -> DifficultyResult:
        """Bank the run: ×5 if every graph hit the max time bonus."""
        graph_count = len(self.graph_queue)
        all_max = graph_count > 0 and self.max_time_bonus_hits == graph_count
        banked = ScoringSystem.apply_500_percent_bonus(self.provisional_score, all_max)
        self.total_banked += banked
        result = DifficultyResult(
            difficulty=self.difficulty, provisional_score=self.provisional_score,
            banked_score=banked, all_max_time=all_max, resets=self.resets,
            hints_used=self.difficulty_hints_used,
            forfeits=self.forfeits, graph_count=graph_count,
            graphs_completed=sum(1 for r in self.level_results if not r.forfeited))
        result.new_badges = self.take_pending_badges() + self.achievement_system.on_difficulty_completed(
            self.difficulty, self.resets, all_max, self.difficulty_hints_used, self.forfeits)
        result.streak = self.achievement_system.get_streak(self.difficulty)
        self.last_difficulty_result = result
        return result

    def submit_score(self, player_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Put the last difficulty result on the leaderboard (once). Returns (rank, error)."""
        result = self.last_difficulty_result
        if result is None:
            return None, "No finished run to submit."
        if result.submitted:
            return None, "Score already submitted."
        name, error = validate_player_name(player_name)
        if error:
            return None, error
        result.leaderboard_rank = self.leaderboard_system.add_entry(
            name, result.difficulty, result.banked_score, result.graphs_completed)
        result.submitted = True
        return result.leaderboard_rank, None

    @staticmethod
    def next_difficulty(difficulty: Optional[str]) -> Optional[str]:
        order = list(DIFFICULTY_CONFIG)
        if difficulty in order and order.index(difficulty) + 1 < len(order):
            return order[order.index(difficulty) + 1]
        return None
