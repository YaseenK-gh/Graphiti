"""Graph generators for all 11 graph types.

Every generator returns ``(vertices, edges)`` where ``vertices == list(range(n))``
and ``edges`` is a list of ``(u, v)`` tuples with ``u < v``, no duplicates and
no self-loops. Every generated graph is connected.

The planar families (TRIANGLE_FREE, NEAR_TRIANGULATION, PLANAR) are carved out
of a Delaunay triangulation of random points, so they come with a crossing-free
straight-line embedding. ``generate_graph_full`` exposes those positions so the
layout engine can draw these graphs without edge crossings.
"""

import heapq
import logging
import random
from collections import deque
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from algorithms.geometry import count_crossings, delaunay_edges, random_points
from core.constants import GENERATION_MAX_RETRIES, GRAPH_CONSTRAINTS

logger = logging.getLogger(__name__)

Edge = Tuple[int, int]
Positions = Dict[int, Tuple[float, float]]
FullResult = Tuple[List[int], List[Edge], Optional[Positions]]


class GenerationError(RuntimeError):
    """A generator produced an invalid graph (retried by generate_graph_by_type)."""


def _norm(u: int, v: int) -> Edge:
    return (u, v) if u < v else (v, u)


def is_connected(n: int, edges: Sequence[Edge]) -> bool:
    if n <= 1:
        return True
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    seen = {0}
    queue = deque([0])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return len(seen) == n


def _random_spanning_tree(n: int, edges: Sequence[Edge], rng) -> List[Edge]:
    """Random spanning tree (randomised Kruskal) using only the given edges."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    shuffled = list(edges)
    rng.shuffle(shuffled)
    tree = []
    for u, v in shuffled:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            tree.append(_norm(u, v))
    return tree


# ─── Easy families ────────────────────────────────────────────────────────────

def generate_path(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """A single chain through all n vertices, visited in random label order."""
    order = list(range(n))
    rng.shuffle(order)
    return list(range(n)), [tuple(sorted((order[i], order[i + 1]))) for i in range(n - 1)]


def generate_tree(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Uniformly random labelled tree via Prüfer sequence decoding."""
    vertices = list(range(n))
    if n <= 1:
        return vertices, []
    if n == 2:
        return vertices, [(0, 1)]

    prufer = [rng.randrange(n) for _ in range(n - 2)]
    degree = [1] * n
    for node in prufer:
        degree[node] += 1

    leaves = [i for i in range(n) if degree[i] == 1]
    heapq.heapify(leaves)
    edges = []
    for node in prufer:
        leaf = heapq.heappop(leaves)
        edges.append(_norm(leaf, node))
        degree[node] -= 1
        if degree[node] == 1:
            heapq.heappush(leaves, node)
    u, v = heapq.heappop(leaves), heapq.heappop(leaves)
    edges.append(_norm(u, v))
    return vertices, edges


def generate_bipartite(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Connected random bipartite graph: A = [0, n//2), B = [n//2, n), ~40% density (capped)."""
    a = n // 2
    set_a = list(range(a))
    set_b = list(range(a, n))
    rng.shuffle(set_a)
    rng.shuffle(set_b)

    # Random spanning tree that alternates sides guarantees connectivity.
    edges = {_norm(set_a[0], set_b[0])}
    joined_a, joined_b = [set_a[0]], [set_b[0]]
    rest = [(v, True) for v in set_a[1:]] + [(v, False) for v in set_b[1:]]
    rng.shuffle(rest)
    for v, in_a in rest:
        other = rng.choice(joined_b if in_a else joined_a)
        edges.add(_norm(v, other))
        (joined_a if in_a else joined_b).append(v)

    max_edges = a * (n - a)
    target = min(max_edges, max(n, min(int(max_edges * 0.4), int(1.5 * n))))
    all_cross = [(u, v) for u in range(a) for v in range(a, n) if (u, v) not in edges]
    rng.shuffle(all_cross)
    for e in all_cross:
        if len(edges) >= target:
            break
        edges.add(e)
    return list(range(n)), sorted(edges)


def generate_cycle(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Ring: 0-1-2-...-n-1-0"""
    return list(range(n)), [_norm(i, (i + 1) % n) for i in range(n)]


# ─── Medium families ──────────────────────────────────────────────────────────

def generate_complete_bipartite(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Complete bipartite K_{a,b} with a = floor(n/2), b = ceil(n/2)."""
    a = n // 2
    return list(range(n)), [(u, v) for u in range(a) for v in range(a, n)]


def generate_wheel(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Hub (node 0) + rim cycle (nodes 1 to n-1)."""
    edges = [(0, i) for i in range(1, n)]
    edges += [(i, i + 1) for i in range(1, n - 1)]
    edges.append((1, n - 1))  # Close the rim.
    return list(range(n)), edges


def generate_outerplanar(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Randomly triangulated convex polygon with some chords removed.

    Vertices 0..n-1 are in boundary order, so drawing them on a circle is
    crossing-free. The boundary cycle is always kept (connectivity).
    """
    edges = {_norm(i, (i + 1) % n) for i in range(n)}
    chords = []
    stack = [list(range(n))]
    while stack:
        poly = stack.pop()
        m = len(poly)
        if m <= 3:
            continue
        i = rng.randrange(m)
        j = (i + rng.randint(2, m - 2)) % m  # Non-adjacent on this sub-polygon.
        if i > j:
            i, j = j, i
        chords.append(_norm(poly[i], poly[j]))
        stack.append(poly[i:j + 1])
        stack.append(poly[j:] + poly[:i + 1])

    rng.shuffle(chords)
    keep = len(chords) - int(len(chords) * rng.uniform(0.1, 0.3))
    edges.update(chords[:keep])
    return list(range(n)), sorted(edges)


def generate_chordal(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    """Chordal graph built in reverse perfect-elimination order.

    Each new vertex attaches to a *clique* of already-placed vertices, so its
    earlier neighbourhood is a clique and the construction order reversed is a
    PEO. Clique size ≤ 3 keeps ω (= χ) ≤ 4.
    """
    order = list(range(n))
    rng.shuffle(order)
    adj = {v: set() for v in range(n)}
    placed = [order[0]]
    for v in order[1:]:
        anchor = rng.choice(placed)
        target = rng.choices([1, 2, 3], weights=[0.35, 0.40, 0.25])[0]
        clique = [anchor]
        candidates = list(adj[anchor])
        rng.shuffle(candidates)
        for w in candidates:
            if len(clique) >= target:
                break
            if all(w in adj[c] for c in clique):
                clique.append(w)
        for c in clique:
            adj[v].add(c)
            adj[c].add(v)
        placed.append(v)
    edges = sorted({_norm(u, v) for u in adj for v in adj[u]})
    return list(range(n)), edges


# ─── Hard (planar) families ───────────────────────────────────────────────────

def _delaunay_base(n: int, rng) -> Tuple[List[Edge], Positions]:
    points = random_points(n, rng)
    return sorted(delaunay_edges(points)), {i: points[i] for i in range(n)}


def generate_triangle_free_full(n: int, rng=random) -> FullResult:
    """Maximal triangle-free subgraph of a Delaunay triangulation (planar, χ ≤ 3)."""
    base, positions = _delaunay_base(n, rng)
    adj = [set() for _ in range(n)]
    edges = []
    for u, v in _random_spanning_tree(n, base, rng):  # A tree has no triangles.
        adj[u].add(v)
        adj[v].add(u)
        edges.append((u, v))
    tree = set(edges)
    rest = [e for e in base if e not in tree]
    rng.shuffle(rest)
    for u, v in rest:
        if not adj[u] & adj[v]:  # No common neighbour ⇒ adding u-v makes no triangle.
            adj[u].add(v)
            adj[v].add(u)
            edges.append((u, v))
    return list(range(n)), sorted(edges), positions


def generate_near_triangulation_full(n: int, rng=random) -> FullResult:
    """Delaunay triangulation: planar, every interior face a triangle."""
    edges, positions = _delaunay_base(n, rng)
    return list(range(n)), edges, positions


def generate_planar_full(n: int, rng=random) -> FullResult:
    """Delaunay triangulation with 20–35% of edges removed (never disconnecting)."""
    base, positions = _delaunay_base(n, rng)
    tree = set(_random_spanning_tree(n, base, rng))
    removable = [e for e in base if e not in tree]
    rng.shuffle(removable)
    remove_count = min(len(removable), int(len(base) * rng.uniform(0.2, 0.35)))
    removed = set(removable[:remove_count])
    return list(range(n)), [e for e in base if e not in removed], positions


def generate_triangle_free(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    return generate_triangle_free_full(n, rng)[:2]


def generate_near_triangulation(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    return generate_near_triangulation_full(n, rng)[:2]


def generate_planar(n: int, rng=random) -> Tuple[List[int], List[Edge]]:
    return generate_planar_full(n, rng)[:2]


# ─── Dispatch with validation + retry ─────────────────────────────────────────

def _no_positions(fn: Callable) -> Callable[[int, object], FullResult]:
    return lambda n, rng: (*fn(n, rng), None)


GENERATORS: Dict[str, Callable[[int, object], FullResult]] = {
    'PATH': _no_positions(generate_path),
    'TREE': _no_positions(generate_tree),
    'BIPARTITE': _no_positions(generate_bipartite),
    'CYCLE': _no_positions(generate_cycle),
    'COMPLETE_BIPARTITE': _no_positions(generate_complete_bipartite),
    'WHEEL': _no_positions(generate_wheel),
    'OUTERPLANAR': _no_positions(generate_outerplanar),
    'CHORDAL': _no_positions(generate_chordal),
    'TRIANGLE_FREE': generate_triangle_free_full,
    'NEAR_TRIANGULATION': generate_near_triangulation_full,
    'PLANAR': generate_planar_full,
}


def validate_graph(n: int, vertices: List[int], edges: Sequence[Edge],
                   positions: Optional[Positions] = None) -> None:
    """Raise GenerationError unless the graph is simple, connected and (if embedded) crossing-free."""
    if vertices != list(range(n)):
        raise GenerationError("vertex list must be 0..n-1")
    seen = set()
    for u, v in edges:
        if not (0 <= u < v < n):
            raise GenerationError(f"invalid edge ({u}, {v})")
        if (u, v) in seen:
            raise GenerationError(f"duplicate edge ({u}, {v})")
        seen.add((u, v))
    if not is_connected(n, edges):
        raise GenerationError("graph is disconnected")
    if positions is not None and count_crossings(edges, positions):
        raise GenerationError("embedding has edge crossings")


def generate_graph_full(graph_type: str, n: int, max_retries: int = GENERATION_MAX_RETRIES,
                        rng=None) -> FullResult:
    """Generate and validate a graph, retrying on failure. Returns (vertices, edges, positions|None)."""
    if graph_type not in GENERATORS:
        raise ValueError(f"Unknown graph type: {graph_type}")
    min_n, max_n = GRAPH_CONSTRAINTS[graph_type]
    if not isinstance(n, int) or not (min_n <= n <= max_n):
        raise ValueError(f"n={n} outside constraints for {graph_type} ({min_n}-{max_n})")
    rng = rng or random

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            vertices, edges, positions = GENERATORS[graph_type](n, rng)
            validate_graph(n, vertices, edges, positions)
            return vertices, edges, positions
        except Exception as e:  # noqa: BLE001 — any failure is retried, then re-raised
            last_error = e
            logger.warning("Generation attempt %d/%d for %s (n=%d) failed: %s",
                           attempt, max_retries, graph_type, n, e)
    raise GenerationError(
        f"Could not generate {graph_type} with n={n} after {max_retries} attempts: {last_error}")


def generate_graph_by_type(graph_type: str, n: int, max_retries: int = GENERATION_MAX_RETRIES,
                           rng=None) -> Tuple[List[int], List[Edge]]:
    """Generate graph with error handling and retry logic. Returns (vertices, edges)."""
    vertices, edges, _ = generate_graph_full(graph_type, n, max_retries, rng)
    return vertices, edges
