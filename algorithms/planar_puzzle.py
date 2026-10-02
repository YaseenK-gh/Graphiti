import math
import random
import time
from dataclasses import dataclass
from typing import List, Sequence, Set, Tuple

from core.constants import PLANAR_MAX_N, PLANAR_MIN_N

Point = Tuple[int, int]
Edge = Tuple[int, int]
Measure = Tuple[float, int]


def orient(a: Point, b: Point, c: Point) -> int:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a: Point, b: Point, p: Point) -> bool:
    return (orient(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def segments_conflict(a: Point, b: Point, c: Point, d: Point) -> bool:
    shared = {a, b} & {c, d}
    if shared:
        s = next(iter(shared))
        p = b if a == s else a
        q = d if c == s else c
        return (orient(s, p, q) == 0
                and (p[0] - s[0]) * (q[0] - s[0]) + (p[1] - s[1]) * (q[1] - s[1]) > 0)
    if orient(a, b, c) * orient(a, b, d) < 0 and orient(c, d, a) * orient(c, d, b) < 0:
        return True
    return on_segment(a, b, c) or on_segment(a, b, d) or on_segment(c, d, a) or on_segment(c, d, b)


def conflicts(edges: Sequence[Edge], pos: Sequence[Point]) -> Set[int]:
    bad: Set[int] = set()
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            if segments_conflict(pos[a], pos[b], pos[c], pos[d]):
                bad.update((i, j))
    return bad


def faces(n: int, edges: Sequence[Edge], pos: Sequence[Point]) -> List[Tuple[int, List[int]]]:
    around: List[List[int]] = [[] for _ in range(n)]
    for a, b in edges:
        around[a].append(b)
        around[b].append(a)
    for v, nbrs in enumerate(around):
        nbrs.sort(key=lambda u: math.atan2(pos[u][1] - pos[v][1], pos[u][0] - pos[v][0]))
    seen, found = set(), []
    for a, b in edges:
        for start in ((a, b), (b, a)):
            walk, (u, v) = [], start
            while (u, v) not in seen:
                seen.add((u, v))
                walk.append(u)
                nbrs = around[v]
                u, v = v, nbrs[nbrs.index(u) - 1]
            if walk:
                twice = sum(pos[p][0] * pos[q][1] - pos[q][0] * pos[p][1]
                            for p, q in zip(walk, walk[1:] + walk[:1]))
                found.append((twice, walk))
    return found


def enclosed_faces(n: int, edges: Sequence[Edge], pos: Sequence[Point]) -> List[List[int]]:
    return [walk for twice, walk in faces(n, edges, pos) if twice > 0]


def enclosed_area(n: int, edges: Sequence[Edge], pos: Sequence[Point]) -> float:
    return sum(abs(twice) for twice, _ in faces(n, edges, pos)) / 4


def bounding_box(pos: Sequence[Point]) -> int:
    xs, ys = [p[0] for p in pos], [p[1] for p in pos]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def measure(n: int, edges: Sequence[Edge], pos: Sequence[Point]) -> Measure:
    return enclosed_area(n, edges, pos), bounding_box(pos)


def bridgeless(n: int, edges: Sequence[Edge]) -> bool:
    adj: List[List[Tuple[int, int]]] = [[] for _ in range(n)]
    for i, (a, b) in enumerate(edges):
        adj[a].append((b, i))
        adj[b].append((a, i))
    order, low, state = [-1] * n, [0] * n, {"count": 0, "ok": True}

    def visit(v: int, via: int):
        order[v] = low[v] = state["count"]
        state["count"] += 1
        for u, i in adj[v]:
            if i == via:
                continue
            if order[u] == -1:
                visit(u, i)
                low[v] = min(low[v], low[u])
                if low[u] > order[v]:
                    state["ok"] = False
            else:
                low[v] = min(low[v], order[u])

    visit(0, -1)
    return state["ok"] and state["count"] == n


def make_graph(n: int, density: float, rng=random) -> Tuple[List[Edge], List[Point]]:
    side = math.isqrt(n - 1) + 3
    cells = [(x, y) for x in range(side) for y in range(side)]
    while True:
        solution = rng.sample(cells, n)
        pairs = sorted(((a, b) for a in range(n) for b in range(a + 1, n)),
                       key=lambda e: (math.dist(solution[e[0]], solution[e[1]]), rng.random()))
        edges: List[Edge] = []
        for a, b in pairs:
            if any(on_segment(solution[a], solution[b], solution[w])
                   for w in range(n) if w not in (a, b)):
                continue
            if any(segments_conflict(solution[a], solution[b], solution[c], solution[d])
                   for c, d in edges):
                continue
            edges.append((a, b))
        if not bridgeless(n, edges):
            continue
        target = max(n, round(density * n))
        removable = edges[:]
        rng.shuffle(removable)
        for edge in removable:
            if len(edges) <= target:
                break
            rest = [e for e in edges if e != edge]
            if bridgeless(n, rest):
                edges = rest
        return edges, solution


def scramble(n: int, edges: Sequence[Edge], cols: int, rows: int, rng=random) -> List[Point]:
    cells = [(x, y) for x in range(cols + 1) for y in range(rows + 1)]
    wanted = max(4, len(edges) // 2)
    pos = rng.sample(cells, n)
    for _ in range(300):
        if len(conflicts(edges, pos)) >= wanted:
            break
        pos = rng.sample(cells, n)
    return pos


@dataclass
class PlanarPuzzle:
    index: int
    n: int
    edges: List[Edge]
    cols: int
    rows: int
    start: List[Point]
    solution: List[Point]


def puzzle_size(index: int, rng=random) -> Tuple[int, float]:
    n = min(PLANAR_MAX_N, PLANAR_MIN_N + index // 2 + rng.randint(0, 1))
    return n, min(2.2, 1.3 + 0.1 * index)


def build_puzzle(index: int, rng=random) -> PlanarPuzzle:
    n, density = puzzle_size(index, rng)
    cols, rows = 10 + n // 2, 6 + n // 3
    edges, solution = make_graph(n, density, rng)
    return PlanarPuzzle(index=index, n=n, edges=edges, cols=cols, rows=rows,
                        start=scramble(n, edges, cols, rows, rng), solution=solution)


class Compactor:
    def __init__(self, puzzle: PlanarPuzzle, rng=random):
        self.puzzle = puzzle
        self.rng = rng
        self.pos: List[Point] = list(puzzle.solution)
        self.key: Measure = measure(puzzle.n, puzzle.edges, self.pos)
        self.incident = [[i for i, e in enumerate(puzzle.edges) if v in e] for v in range(puzzle.n)]

    def step(self) -> bool:
        puzzle, pos, edges = self.puzzle, self.pos, self.puzzle.edges
        v = self.rng.randrange(puzzle.n)
        old = pos[v]
        new = (old[0] + self.rng.randint(-2, 2), old[1] + self.rng.randint(-2, 2))
        if new in pos or not (0 <= new[0] <= puzzle.cols and 0 <= new[1] <= puzzle.rows):
            return False
        pos[v] = new
        clash = any(segments_conflict(pos[edges[i][0]], pos[edges[i][1]], pos[c], pos[d])
                    for i in self.incident[v] for j, (c, d) in enumerate(edges) if j != i)
        trial = None if clash else measure(puzzle.n, edges, pos)
        if trial is not None and trial <= self.key:
            improved = trial < self.key
            self.key = trial
            return improved
        pos[v] = old
        return False

    def run(self, seconds: float):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.step()
