import logging
import time
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

from core.constants import CHROMATIC_FALLBACK, CHROMATIC_TIMEOUT_MS

logger = logging.getLogger(__name__)

AdjList = List[List[int]]


class SolverTimeout(TimeoutError):
    pass


def make_deadline(timeout_ms: Optional[float]) -> Optional[float]:
    return None if timeout_ms is None else time.perf_counter() + timeout_ms / 1000.0


def build_adjacency_list(n: int, edges: Sequence[Tuple[int, int]]) -> AdjList:
    adj: AdjList = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def is_bipartite(adj_list: AdjList, n: int) -> bool:
    color = [-1] * n
    for start in range(n):
        if color[start] != -1:
            continue
        color[start] = 0
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in adj_list[u]:
                if color[v] == -1:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return False
    return True


def has_triangle(adj_list: AdjList, n: int) -> bool:
    nbrs = [set(a) for a in adj_list]
    for u in range(n):
        for v in adj_list[u]:
            if v > u and nbrs[u] & nbrs[v]:
                return True
    return False


def find_max_clique_size(adj_list: AdjList, n: int, timeout_ms: Optional[float] = None) -> int:
    if n == 0:
        return 0
    nbrs = [set(a) for a in adj_list]
    deadline = make_deadline(timeout_ms)
    best = [1]
    calls = [0]

    def expand(size: int, p: set, x: set):
        calls[0] += 1
        if deadline is not None and calls[0] % 256 == 0 and time.perf_counter() > deadline:
            raise SolverTimeout("max clique search timed out")
        if not p and not x:
            best[0] = max(best[0], size)
            return
        if size + len(p) <= best[0]:
            return
        pivot = max(p | x, key=lambda u: len(p & nbrs[u]))
        for v in list(p - nbrs[pivot]):
            expand(size + 1, p & nbrs[v], x & nbrs[v])
            p.remove(v)
            x.add(v)

    expand(0, set(range(n)), set())
    return best[0]


def maximum_cardinality_search(adj_list: AdjList, n: int) -> List[int]:
    weight = [0] * n
    numbered = [False] * n
    order = []
    for _ in range(n):
        v = max((u for u in range(n) if not numbered[u]), key=lambda u: weight[u])
        numbered[v] = True
        order.append(v)
        for u in adj_list[v]:
            if not numbered[u]:
                weight[u] += 1
    return order


def is_chordal(adj_list: AdjList, n: int) -> bool:
    order = maximum_cardinality_search(adj_list, n)
    pos = {v: i for i, v in enumerate(order)}
    nbrs = [set(a) for a in adj_list]
    for v in order:
        earlier = [u for u in adj_list[v] if pos[u] < pos[v]]
        if not earlier:
            continue
        parent = max(earlier, key=lambda u: pos[u])
        if any(u != parent and u not in nbrs[parent] for u in earlier):
            return False
    return True


def chordal_clique_number(adj_list: AdjList, n: int) -> int:
    if n == 0:
        return 0
    order = maximum_cardinality_search(adj_list, n)
    pos = {v: i for i, v in enumerate(order)}
    return max(1 + sum(1 for u in adj_list[v] if pos[u] < pos[v]) for v in range(n))


def dsatur_coloring(adj_list: AdjList, n: int) -> List[int]:
    color = [-1] * n
    saturation = [set() for _ in range(n)]
    degree = [len(a) for a in adj_list]
    for _ in range(n):
        v = max((u for u in range(n) if color[u] == -1),
                key=lambda u: (len(saturation[u]), degree[u]))
        c = 0
        while c in saturation[v]:
            c += 1
        color[v] = c
        for u in adj_list[v]:
            saturation[u].add(c)
    return color


def extend_coloring(adj_list: AdjList, n: int, max_colors: int,
                    precolored: Optional[Dict[int, Optional[int]]] = None,
                    palette_size: Optional[int] = None,
                    deadline: Optional[float] = None) -> Optional[List[int]]:
    palette_size = max_colors if palette_size is None else palette_size
    color = [-1] * n
    use = [0] * palette_size
    nb_colors: List[Dict[int, int]] = [dict() for _ in range(n)]
    degree = [len(a) for a in adj_list]

    def assign(v: int, c: int):
        color[v] = c
        use[c] += 1
        for u in adj_list[v]:
            d = nb_colors[u]
            d[c] = d.get(c, 0) + 1

    def unassign(v: int, c: int):
        color[v] = -1
        use[c] -= 1
        for u in adj_list[v]:
            d = nb_colors[u]
            left = d[c] - 1
            if left:
                d[c] = left
            else:
                del d[c]

    for v, c in (precolored or {}).items():
        if c is None:
            continue
        if not 0 <= c < palette_size or c in nb_colors[v]:
            return None
        assign(v, c)
    if sum(1 for k in use if k) > max_colors:
        return None

    nodes = [0]

    def pick() -> int:
        best, best_sat, best_deg = -1, -1, -1
        for v in range(n):
            if color[v] == -1:
                s = len(nb_colors[v])
                if s > best_sat or (s == best_sat and degree[v] > best_deg):
                    best, best_sat, best_deg = v, s, degree[v]
        return best

    def solve(remaining: int) -> bool:
        if remaining == 0:
            return True
        nodes[0] += 1
        if deadline is not None and (nodes[0] & 127) == 0 and time.perf_counter() > deadline:
            raise SolverTimeout("coloring search timed out")
        v = pick()
        forbidden = nb_colors[v]
        candidates = [c for c in range(palette_size) if use[c] and c not in forbidden]
        if sum(1 for k in use if k) < max_colors:
            fresh = next((c for c in range(palette_size) if not use[c]), None)
            if fresh is not None:
                candidates.append(fresh)
        for c in candidates:
            assign(v, c)
            if solve(remaining - 1):
                return True
            unassign(v, c)
        return False

    return color if solve(color.count(-1)) else None


def can_color_with_k(adj_list: AdjList, n: int, k: int, deadline: Optional[float] = None) -> bool:
    return extend_coloring(adj_list, n, k, deadline=deadline) is not None


def solve_chromatic(adj_list: AdjList, n: int,
                    timeout_ms: Optional[float] = CHROMATIC_TIMEOUT_MS) -> Tuple[int, List[int], bool]:
    if n == 0:
        return 0, [], True
    if not any(adj_list):
        return 1, [0] * n, True
    greedy = dsatur_coloring(adj_list, n)
    upper = max(greedy) + 1
    lower = 3 if has_triangle(adj_list, n) else 2
    if lower >= upper:
        return upper, greedy, True
    deadline = make_deadline(timeout_ms)
    try:
        for k in range(lower, upper):
            coloring = extend_coloring(adj_list, n, k, deadline=deadline)
            if coloring is not None:
                return k, coloring, True
        return upper, greedy, True
    except SolverTimeout:
        return upper, greedy, False


def backtrack_chromatic_number(adj_list: AdjList, n: int,
                               timeout_ms: float = CHROMATIC_TIMEOUT_MS,
                               fallback: int = CHROMATIC_FALLBACK) -> int:
    k, _, exact = solve_chromatic(adj_list, n, timeout_ms)
    if not exact:
        k = min(fallback, k)
        logger.warning("Chromatic number timeout after %sms, using fallback k=%d", timeout_ms, k)
    return k


def compute_chromatic_number(graph_type: str, n: int, edges: Sequence[Tuple[int, int]],
                             timeout_ms: float = CHROMATIC_TIMEOUT_MS) -> int:
    if n == 0:
        return 0
    if not edges:
        return 1

    if graph_type in ('PATH', 'TREE', 'BIPARTITE', 'COMPLETE_BIPARTITE'):
        return 2
    if graph_type == 'CYCLE':
        return 2 if n % 2 == 0 else 3
    if graph_type == 'WHEEL':
        rim_size = n - 1
        return 3 if rim_size % 2 == 0 else 4

    adj_list = build_adjacency_list(n, edges)
    if graph_type in ('OUTERPLANAR', 'TRIANGLE_FREE'):
        return 2 if is_bipartite(adj_list, n) else 3
    if graph_type == 'CHORDAL':
        return chordal_clique_number(adj_list, n)
    return backtrack_chromatic_number(adj_list, n, timeout_ms)


def optimal_coloring(n: int, edges: Sequence[Tuple[int, int]],
                     chromatic_number: Optional[int] = None,
                     timeout_ms: float = CHROMATIC_TIMEOUT_MS) -> Dict[int, int]:
    adj_list = build_adjacency_list(n, edges)
    if chromatic_number:
        try:
            coloring = extend_coloring(adj_list, n, chromatic_number,
                                       deadline=make_deadline(timeout_ms))
            if coloring is not None:
                return dict(enumerate(coloring))
        except SolverTimeout:
            pass
    _, coloring, _ = solve_chromatic(adj_list, n, timeout_ms)
    return dict(enumerate(coloring))
