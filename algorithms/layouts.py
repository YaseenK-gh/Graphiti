"""Layout engine: vertex positions in a CANVAS_WIDTH × CANVAS_HEIGHT scene.

Every layout returns ``{vertex_id: (x, y)}`` with all points inside the padded
canvas. PATH and TREE are deliberately tangled to make them harder to read; the
other families show their structure without crossings where possible, with
force-directed placement as the fallback for CHORDAL (and planar graphs without
an embedding).
"""

import logging
import math
import random
import time
from typing import Dict, List, Optional, Sequence, Tuple

from algorithms.geometry import count_crossings
from core.constants import (CANVAS_HEIGHT, CANVAS_PADDING, CANVAS_WIDTH, LAYOUT_TIMEOUT_MS,
                            NODE_RADIUS_MAX, NODE_RADIUS_MIN, NODE_RADIUS_SCALE)

logger = logging.getLogger(__name__)

LayoutDict = Dict[int, Tuple[float, float]]
Edge = Tuple[int, int]


def vertex_radius(n: int) -> float:
    """Node radius: clamp(300 / n, 8, 14)."""
    return max(NODE_RADIUS_MIN, min(NODE_RADIUS_MAX, NODE_RADIUS_SCALE / max(n, 1)))


def compute_layout(graph_type: str, n: int, vertices: Sequence[int], edges: Sequence[Edge],
                   positions: Optional[LayoutDict] = None,
                   width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT,
                   padding: int = CANVAS_PADDING,
                   timeout_ms: float = LAYOUT_TIMEOUT_MS) -> LayoutDict:
    """Compute layout based on graph type (or scale a known planar embedding)."""
    if n == 0:
        return {}
    if positions:
        return layout_from_positions(positions, width, height, padding)
    if graph_type in ('PATH', 'TREE'):
        return layout_tangled(n, edges, width, height, padding, timeout_ms)
    if graph_type in ('BIPARTITE', 'COMPLETE_BIPARTITE'):
        return layout_two_columns(n, vertices, edges, width, height, padding)
    if graph_type in ('CYCLE', 'OUTERPLANAR'):
        return layout_circle(n, width, height, padding)
    if graph_type == 'WHEEL':
        return layout_wheel(n, width, height, padding)
    return layout_force_directed(n, vertices, edges, width, height, padding, timeout_ms)


def layout_from_positions(positions: LayoutDict, width: int, height: int, padding: int) -> LayoutDict:
    """Affinely scale an embedding into the canvas (affine maps keep it crossing-free)."""
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    fx = _fit_axis(xs, padding, width - padding)
    fy = _fit_axis(ys, padding, height - padding)
    return {v: (fx(x), fy(y)) for v, (x, y) in positions.items()}


def _fit_axis(values: Sequence[float], lo: float, hi: float):
    vmin, vmax = min(values), max(values)
    span = vmax - vmin
    if span < 1e-9:
        mid = (lo + hi) / 2
        return lambda _v: mid
    return lambda v: lo + (v - vmin) / span * (hi - lo)


def layout_circle(n: int, width: int, height: int, padding: int) -> LayoutDict:
    """Circle layout: vertices on a regular polygon, starting at the top."""
    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - padding
    return {i: (cx + radius * math.cos(2 * math.pi * i / n - math.pi / 2),
                cy + radius * math.sin(2 * math.pi * i / n - math.pi / 2)) for i in range(n)}


def layout_wheel(n: int, width: int, height: int, padding: int) -> LayoutDict:
    """Wheel layout: hub (vertex 0) at the centre, rim on a circle."""
    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - padding
    rim = n - 1
    layout = {0: (cx, cy)}
    for i in range(1, n):
        angle = 2 * math.pi * (i - 1) / rim - math.pi / 2
        layout[i] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    return layout


def _adjacency(n: int, edges: Sequence[Edge]) -> List[List[int]]:
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def layout_two_columns(n: int, vertices: Sequence[int], edges: Sequence[Edge],
                       width: int, height: int, padding: int, sweeps: int = 4) -> LayoutDict:
    """Two-column layout: set A = [0, n//2) left, set B right, barycenter-ordered to cut crossings."""
    a = n // 2
    left, right = list(range(a)), list(range(a, n))
    adj = _adjacency(n, edges)
    pos = {v: i for i, v in enumerate(left)}
    pos.update({v: i for i, v in enumerate(right)})

    def barycenter(v: int) -> float:
        return sum(pos[u] for u in adj[v]) / len(adj[v]) if adj[v] else pos[v]

    for _ in range(sweeps):
        for column in (right, left):
            column.sort(key=lambda v: (barycenter(v), pos[v]))
            pos.update({v: i for i, v in enumerate(column)})

    layout = {}
    layout.update(_column(left, width * 0.25, height, padding))
    layout.update(_column(right, width * 0.75, height, padding))
    return layout


def _column(vs: List[int], x: float, height: int, padding: int, max_gap: float = 70.0) -> LayoutDict:
    if not vs:
        return {}
    if len(vs) == 1:
        return {vs[0]: (x, height / 2)}
    gap = min(max_gap, (height - 2 * padding) / (len(vs) - 1))
    top = height / 2 - gap * (len(vs) - 1) / 2
    return {v: (x, top + i * gap) for i, v in enumerate(vs)}


def edge_clearance(n: int) -> float:
    """How far an edge must stay from every vertex it doesn't connect to."""
    return vertex_radius(n) + 5.0


def _segment_dist2(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Squared distance from point p to segment ab."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    cx, cy = ax + t * dx - px, ay + t * dy - py
    return cx * cx + cy * cy


def edges_grazing_vertices(edges: Sequence[Edge], layout: LayoutDict, clearance: float) -> int:
    """Count (edge, vertex) pairs where an edge runs within `clearance` of a vertex it doesn't touch."""
    c2 = clearance * clearance
    count = 0
    for u, v in edges:
        (ax, ay), (bx, by) = layout[u], layout[v]
        for w, (px, py) in layout.items():
            if w != u and w != v and _segment_dist2(px, py, ax, ay, bx, by) < c2:
                count += 1
    return count


def layout_tangled(n: int, edges: Sequence[Edge], width: int, height: int, padding: int,
                   timeout_ms: float = LAYOUT_TIMEOUT_MS, rng=random,
                   spare_cells: float = 1.35, max_attempts: int = 8) -> LayoutDict:
    """Scatter vertices over a jittered grid in random order so edges cross everywhere,
    then shuffle positions until no edge runs through a vertex it doesn't connect to."""
    if n == 1:
        return {0: (width / 2, height / 2)}
    start_time = time.perf_counter()
    budget_s = min(timeout_ms, 600.0) / 1000

    # Small graphs use a smaller central region so they don't look lost on the canvas.
    scale = max(0.5, min(1.0, math.sqrt(n / 20)))
    w, h = (width - 2 * padding) * scale, (height - 2 * padding) * scale
    x0, y0 = (width - w) / 2, (height - h) / 2
    cells = max(n + 2, math.ceil(n * spare_cells))
    cols = max(2, math.ceil(math.sqrt(cells * w / h)))
    rows = max(2, math.ceil(cells / cols))
    cw, ch = w / cols, h / rows
    slots = [(x0 + (c + 0.5 + rng.uniform(-0.3, 0.3)) * cw, y0 + (r + 0.5 + rng.uniform(-0.3, 0.3)) * ch)
             for r in range(rows) for c in range(cols)]

    incident: List[List[int]] = [[] for _ in range(n)]
    for i, (u, v) in enumerate(edges):
        incident[u].append(i)
        incident[v].append(i)
    c2 = edge_clearance(n) ** 2

    def near(e: int, w_: int, where: List[int]) -> bool:
        u, v = edges[e]
        if w_ == u or w_ == v:
            return False
        (ax, ay), (bx, by), (px, py) = slots[where[u]], slots[where[v]], slots[where[w_]]
        return _segment_dist2(px, py, ax, ay, bx, by) < c2

    def pairs_touching(vs, where: List[int]) -> set:
        found = set()
        for x in vs:
            for e in range(len(edges)):  # x sitting on someone else's edge
                if near(e, x, where):
                    found.add((e, x))
            for e in incident[x]:  # x's edges running over someone else
                for w_ in range(n):
                    if near(e, w_, where):
                        found.add((e, w_))
        return found

    def attempt(deadline: float):
        where = rng.sample(range(len(slots)), n)  # vertex -> slot index
        occupant: List[Optional[int]] = [None] * len(slots)
        for v, s in enumerate(where):
            occupant[s] = v
        bad = pairs_touching(range(n), where)
        while bad and time.perf_counter() < deadline:
            # Move a vertex of a bad pair to a random slot (swapping with whoever is there).
            e, w_ = rng.choice(tuple(bad))
            a = rng.choice((w_, *edges[e]))
            target = rng.randrange(len(slots))
            b = occupant[target]
            if b == a:
                continue
            movers = (a,) if b is None else (a, b)
            before = pairs_touching(movers, where)
            sa = where[a]
            where[a], occupant[target], occupant[sa] = target, a, b
            if b is not None:
                where[b] = sa
            after = pairs_touching(movers, where)
            if len(after) < len(before) or (len(after) == len(before) and rng.random() < 0.3):
                bad = (bad - before) | after
            else:  # Undo.
                where[a], occupant[sa], occupant[target] = sa, a, b
                if b is not None:
                    where[b] = target
        layout = {v: slots[where[v]] for v in range(n)}
        return len(bad), -count_crossings(edges, layout), layout

    # Keep the most tangled of a few clean attempts (small graphs vary a lot).
    deadline = start_time + budget_s
    best = attempt(deadline)
    for _ in range(max_attempts - 1):
        if time.perf_counter() - start_time > budget_s / 3:
            break
        best = min(best, attempt(deadline), key=lambda r: r[:2])
    if best[0]:
        logger.warning("Tangled layout left %d edge/vertex near-misses (n=%d)", best[0], n)
    return best[2]


def layout_force_directed(n: int, vertices: Sequence[int], edges: Sequence[Edge],
                          width: int, height: int, padding: int,
                          timeout_ms: float = LAYOUT_TIMEOUT_MS, rng=random) -> LayoutDict:
    """Fruchterman–Reingold with an iteration cap and a wall-clock timeout."""
    start_time = time.perf_counter()
    if n == 1:
        return {0: (width / 2, height / 2)}

    iterations = 100 if n > 40 else 150 if n > 30 else 200
    w, h = width - 2 * padding, height - 2 * padding
    cx, cy = width / 2, height / 2
    k = 0.8 * math.sqrt(w * h / n)
    k2 = k * k

    # Start on a jittered circle: far fewer tangles than uniform random starts.
    r0 = min(w, h) / 3
    xs, ys = [], []
    for i in range(n):
        angle = 2 * math.pi * i / n
        xs.append(cx + r0 * math.cos(angle) + rng.uniform(-5, 5))
        ys.append(cy + r0 * math.sin(angle) + rng.uniform(-5, 5))

    temperature = w / 10
    cooling = temperature / (iterations + 1)
    for iteration in range(iterations):
        if iteration % 20 == 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if elapsed_ms > timeout_ms:
                logger.warning("Layout timeout after %.0fms, stopping at iteration %d",
                               elapsed_ms, iteration)
                break

        dx = [0.0] * n
        dy = [0.0] * n
        for i in range(n):  # Repulsion k²/d between all pairs.
            xi, yi = xs[i], ys[i]
            for j in range(i + 1, n):
                ddx, ddy = xi - xs[j], yi - ys[j]
                d2 = ddx * ddx + ddy * ddy
                if d2 < 0.01:
                    ddx, ddy = rng.uniform(-1, 1), rng.uniform(-1, 1)
                    d2 = ddx * ddx + ddy * ddy + 0.01
                f = k2 / d2
                dx[i] += ddx * f
                dy[i] += ddy * f
                dx[j] -= ddx * f
                dy[j] -= ddy * f
        for u, v in edges:  # Attraction d²/k along edges.
            ddx, ddy = xs[u] - xs[v], ys[u] - ys[v]
            f = math.sqrt(ddx * ddx + ddy * ddy) / k
            dx[u] -= ddx * f
            dy[u] -= ddy * f
            dx[v] += ddx * f
            dy[v] += ddy * f
        for i in range(n):  # Move, capped by temperature; weak gravity keeps it centred.
            fx = dx[i] + (cx - xs[i]) * 0.02
            fy = dy[i] + (cy - ys[i]) * 0.02
            d = math.sqrt(fx * fx + fy * fy)
            if d > 0:
                step = min(d, temperature) / d
                xs[i] = min(width - padding, max(padding, xs[i] + fx * step))
                ys[i] = min(height - padding, max(padding, ys[i] + fy * step))
        temperature = max(temperature - cooling, 1.0)

    fx_axis = _fit_axis(xs, padding, width - padding)
    fy_axis = _fit_axis(ys, padding, height - padding)
    xs = [fx_axis(x) for x in xs]
    ys = [fy_axis(y) for y in ys]
    _separate(xs, ys, 3 * vertex_radius(n), width, height, padding)
    return {i: (xs[i], ys[i]) for i in range(n)}


def _separate(xs: List[float], ys: List[float], min_sep: float,
              width: int, height: int, padding: int, passes: int = 12) -> None:
    """Push apart any nodes closer than `min_sep` (in place)."""
    n = len(xs)
    min_sep2 = min_sep * min_sep
    for _ in range(passes):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                ddx, ddy = xs[j] - xs[i], ys[j] - ys[i]
                d2 = ddx * ddx + ddy * ddy
                if d2 >= min_sep2:
                    continue
                d = math.sqrt(d2) or 0.01
                push = (min_sep - d) / 2
                ux, uy = (ddx / d, ddy / d) if d2 > 0 else (1.0, 0.0)
                xs[i] = min(width - padding, max(padding, xs[i] - ux * push))
                ys[i] = min(height - padding, max(padding, ys[i] - uy * push))
                xs[j] = min(width - padding, max(padding, xs[j] + ux * push))
                ys[j] = min(height - padding, max(padding, ys[j] + uy * push))
                moved = True
        if not moved:
            break
