from typing import Dict, List, Optional, Set, Tuple

Coloring = Dict[int, Optional[int]]


def edge_key(u: int, v: int) -> str:
    return f"{min(u, v)}-{max(u, v)}"


def detect_conflicts(coloring: Coloring, edges: List[Tuple[int, int]]) -> Set[str]:
    conflicts = set()
    for u, v in edges:
        color_u = coloring.get(u)
        if color_u is not None and color_u == coloring.get(v):
            conflicts.add(edge_key(u, v))
    return conflicts


def conflicting_vertices(coloring: Coloring, edges: List[Tuple[int, int]]) -> Set[int]:
    bad = set()
    for u, v in edges:
        if coloring.get(u) is not None and coloring.get(u) == coloring.get(v):
            bad.update((u, v))
    return bad


def is_graph_colored(coloring: Coloring, n: int) -> bool:
    return all(coloring.get(i) is not None for i in range(n))


def is_valid_coloring(conflicts: Set[str]) -> bool:
    return len(conflicts) == 0


def count_distinct_colors(coloring: Coloring) -> int:
    return len({c for c in coloring.values() if c is not None})


def greedy_solve(edges: List[Tuple[int, int]], n: int) -> Dict[int, int]:
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    coloring: Dict[int, int] = {}
    for v in sorted(range(n), key=lambda i: len(adj[i]), reverse=True):
        used = {coloring[u] for u in adj[v] if u in coloring}
        color = 0
        while color in used:
            color += 1
        coloring[v] = color
    return coloring
