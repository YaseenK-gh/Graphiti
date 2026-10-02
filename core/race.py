import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from algorithms.planar_puzzle import Compactor, PlanarPuzzle, build_puzzle, conflicts, measure
from core.constants import (GRAPH_CONSTRAINTS, GRAPH_TYPES, PALETTE, PLANAR_SEARCH_SECONDS,
                            RACE_COLORING, RACE_DISQUALIFY_BELOW, RACE_SECONDS)
from core.graph_manager import GraphManager

Reply = Tuple[bool, Optional[str]]


@dataclass
class Racer:
    id: int
    name: str
    index: int = 0
    solved: int = 0
    skips: int = 0
    penalty: int = 0
    area: float = 0.0
    box: int = 0
    last_change: float = 0.0
    disqualified: bool = False
    left: bool = False

    @property
    def score(self) -> int:
        return self.solved - self.penalty

    @property
    def active(self) -> bool:
        return not self.disqualified and not self.left


class Race:
    def __init__(self, mode: str, players: Dict[int, str], rng=None,
                 clock: Callable[[], float] = time.monotonic, duration: Optional[float] = None,
                 search_seconds: float = PLANAR_SEARCH_SECONDS):
        self.mode = mode
        self.rng = rng or random.Random()
        self.clock = clock
        self.duration = RACE_SECONDS[mode] if duration is None else duration
        self.search_seconds = search_seconds
        self.racers: Dict[int, Racer] = {pid: Racer(pid, name) for pid, name in players.items()}
        self.puzzles: List[dict] = []
        self.planar: List[PlanarPuzzle] = []
        self.searches: List[Compactor] = []
        self.best: Dict[int, dict] = {}
        self.started: Optional[float] = None
        self.ended = False
        self._turn = 0

    def start(self):
        self.started = self.clock()
        self.puzzle(0)

    def elapsed(self) -> float:
        return 0.0 if self.started is None else self.clock() - self.started

    def remaining(self) -> float:
        return max(0.0, self.duration - self.elapsed())

    def time_up(self) -> bool:
        return self.started is not None and self.remaining() <= 0

    def running(self) -> bool:
        return self.started is not None and not self.ended and not self.time_up()

    def puzzle(self, index: int) -> dict:
        while len(self.puzzles) <= index:
            self.puzzles.append(self._make_coloring() if self.mode == RACE_COLORING
                                else self._make_planar())
        return self.puzzles[index]

    def _make_coloring(self) -> dict:
        previous = self.puzzles[-1]["type"] if self.puzzles else None
        graph_type = self.rng.choice([t for t in GRAPH_TYPES if t != previous])
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        graph = GraphManager.generate_graph(graph_type, self.rng.randint(lo, hi))
        return {"index": len(self.puzzles), "type": graph.type, "n": graph.n,
                "edges": [list(edge) for edge in graph.edges],
                "layout": [list(graph.layout[v]) for v in range(graph.n)],
                "chi": graph.chromatic_number}

    def _make_planar(self) -> dict:
        puzzle = build_puzzle(len(self.puzzles), self.rng)
        search = Compactor(puzzle, self.rng)
        search.run(self.search_seconds)
        self.planar.append(puzzle)
        self.searches.append(search)
        return {"index": puzzle.index, "n": puzzle.n, "edges": [list(e) for e in puzzle.edges],
                "cols": puzzle.cols, "rows": puzzle.rows, "start": [list(p) for p in puzzle.start]}

    def improve(self, seconds: float):
        if self.searches:
            self._turn = (self._turn + 1) % len(self.searches)
            self.searches[self._turn].run(seconds)

    def skip_cost(self, pid: int) -> int:
        return self.racers[pid].skips + 1

    def _check(self, pid: int, index: int) -> Optional[str]:
        racer = self.racers.get(pid)
        if racer is None:
            return "Unknown player."
        if not self.running():
            return "The match is not running."
        if racer.disqualified:
            return "You are disqualified."
        if racer.left:
            return "You left the match."
        if index != racer.index:
            return "That is not your current graph."
        return None

    def submit(self, pid: int, index: int, data) -> Reply:
        error = self._check(pid, index)
        if error:
            return False, error
        racer = self.racers[pid]
        self.puzzle(index)
        if self.mode == RACE_COLORING:
            error = self._check_coloring(self.puzzles[index], data)
            if error:
                return False, error
        else:
            puzzle = self.planar[index]
            pos = self._positions(puzzle, data)
            if pos is None:
                return False, "That drawing still has crossings."
            key = measure(puzzle.n, puzzle.edges, pos)
            racer.area += key[0]
            racer.box += key[1]
            best = self.best.get(index)
            if best is None or key < best["key"]:
                self.best[index] = {"key": key, "pos": pos, "name": racer.name}
        racer.solved += 1
        racer.index += 1
        racer.last_change = self.elapsed()
        self.puzzle(racer.index)
        return True, None

    @staticmethod
    def _check_coloring(puzzle: dict, data) -> Optional[str]:
        if not isinstance(data, list) or len(data) != puzzle["n"]:
            return "Every vertex needs a color."
        if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < len(PALETTE)
                   for c in data):
            return "Every vertex needs a color."
        if any(data[u] == data[v] for u, v in puzzle["edges"]):
            return "Two joined vertices share a color."
        return None

    @staticmethod
    def _positions(puzzle: PlanarPuzzle, data) -> Optional[List[Tuple[int, int]]]:
        try:
            pos = [(int(x), int(y)) for x, y in data]
        except (TypeError, ValueError):
            return None
        if len(pos) != puzzle.n or len(set(pos)) != puzzle.n:
            return None
        if not all(0 <= x <= puzzle.cols and 0 <= y <= puzzle.rows for x, y in pos):
            return None
        return None if conflicts(puzzle.edges, pos) else pos

    def skip(self, pid: int, index: int) -> Reply:
        if self.mode != RACE_COLORING:
            return False, "There are no skips in planar drawing."
        error = self._check(pid, index)
        if error:
            return False, error
        racer = self.racers[pid]
        racer.skips += 1
        racer.penalty += racer.skips
        racer.index += 1
        racer.last_change = self.elapsed()
        if racer.score < RACE_DISQUALIFY_BELOW:
            racer.disqualified = True
        else:
            self.puzzle(racer.index)
        return True, None

    def leave(self, pid: int):
        if pid in self.racers:
            self.racers[pid].left = True

    def finish(self):
        self.ended = True
        for racer in self.racers.values():
            if racer.solved == 0:
                racer.disqualified = True

    def _order(self, racer: Racer):
        if self.mode == RACE_COLORING:
            return -racer.score, racer.last_change, racer.id
        return -racer.solved, racer.area, racer.box, racer.last_change, racer.id

    def standings(self) -> List[dict]:
        ranked = sorted((r for r in self.racers.values() if not r.disqualified), key=self._order)
        out = sorted((r for r in self.racers.values() if r.disqualified), key=self._order)
        rows = []
        for place, racer in enumerate(ranked + out, 1):
            rows.append({"id": racer.id, "name": racer.name, "solved": racer.solved,
                         "skips": racer.skips, "penalty": racer.penalty, "score": racer.score,
                         "area": racer.area, "box": racer.box, "index": racer.index,
                         "dq": racer.disqualified, "left": racer.left,
                         "rank": None if racer.disqualified else place})
        return rows

    def winner(self) -> Optional[dict]:
        rows = self.standings()
        return rows[0] if rows and not rows[0]["dq"] else None

    def planar_summary(self) -> List[dict]:
        summary = []
        for index, (puzzle, search) in enumerate(zip(self.planar, self.searches)):
            best = self.best.get(index)
            summary.append({
                "index": index, "n": puzzle.n, "edges": [list(e) for e in puzzle.edges],
                "program_pos": [list(p) for p in search.pos], "program_key": list(search.key),
                "best_pos": [list(p) for p in best["pos"]] if best else None,
                "best_key": list(best["key"]) if best else None,
                "best_name": best["name"] if best else None,
            })
        return summary
