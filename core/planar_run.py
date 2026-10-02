import random
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from algorithms.planar_puzzle import (Compactor, Measure, PlanarPuzzle, Point, build_puzzle,
                                      conflicts, measure)
from core.constants import PLANAR_RUN_SECONDS, PLANAR_SEARCH_SECONDS


@dataclass
class PlanarRecord:
    puzzle: PlanarPuzzle
    program_pos: List[Point]
    program_key: Measure
    your_pos: Optional[List[Point]] = None
    your_key: Optional[Measure] = None

    @property
    def solved(self) -> bool:
        return self.your_key is not None


class PlanarRun:
    def __init__(self, duration: float = PLANAR_RUN_SECONDS, rng=None,
                 clock: Callable[[], float] = time.monotonic,
                 search_seconds: float = PLANAR_SEARCH_SECONDS):
        self.duration = duration
        self.rng = rng or random.Random()
        self.clock = clock
        self.search_seconds = search_seconds
        self.records: List[PlanarRecord] = []
        self.started: Optional[float] = None
        self.solved = 0
        self.total_area = 0.0
        self.total_box = 0
        self.last_submit = 0.0
        self.submitted = False
        self.rank: Optional[int] = None
        self._search: Optional[Compactor] = None

    def start(self):
        self.started = self.clock()
        self.next_puzzle()

    def elapsed(self) -> float:
        return 0.0 if self.started is None else self.clock() - self.started

    def remaining(self) -> float:
        return max(0.0, self.duration - self.elapsed())

    def time_up(self) -> bool:
        return self.started is not None and self.remaining() <= 0

    @property
    def current(self) -> PlanarRecord:
        return self.records[-1]

    def next_puzzle(self) -> PlanarRecord:
        puzzle = build_puzzle(len(self.records), self.rng)
        self._search = Compactor(puzzle, self.rng)
        self._search.run(self.search_seconds)
        record = PlanarRecord(puzzle=puzzle, program_pos=list(self._search.pos),
                              program_key=self._search.key)
        self.records.append(record)
        return record

    def improve(self, seconds: float):
        if self._search is None or not self.records:
            return
        self._search.run(seconds)
        record = self.current
        if self._search.key < record.program_key:
            record.program_pos, record.program_key = list(self._search.pos), self._search.key

    def submit(self, pos: Sequence[Point]) -> Optional[Measure]:
        if self.started is None or self.time_up():
            return None
        record = self.current
        puzzle = record.puzzle
        if record.solved or len(set(pos)) != puzzle.n or conflicts(puzzle.edges, pos):
            return None
        key = measure(puzzle.n, puzzle.edges, pos)
        record.your_pos, record.your_key = list(pos), key
        self.solved += 1
        self.total_area += key[0]
        self.total_box += key[1]
        self.last_submit = self.elapsed()
        self.next_puzzle()
        return key

    def rank_key(self) -> Tuple[int, float, int, float]:
        return -self.solved, self.total_area, self.total_box, self.last_submit


def format_area(value: float) -> str:
    return f"{value:g}"
