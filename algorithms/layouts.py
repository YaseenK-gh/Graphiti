import logging
import math
import random
import time
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

from algorithms.geometry import count_crossings
from core.constants import (CANVAS_HEIGHT, CANVAS_PADDING, CANVAS_WIDTH, LAYOUT_TIMEOUT_MS,
                            NODE_RADIUS_MAX, NODE_RADIUS_MIN, NODE_RADIUS_SCALE)

logger = logging.getLogger(__name__)

TREE_LAYOUT_ATTEMPTS = 120
PATH_LAYOUT_ATTEMPTS = 20

LayoutDict = Dict[int, Tuple[float, float]]
Edge = Tuple[int, int]


def vertex_radius(n: int) -> float:
    return max(NODE_RADIUS_MIN, min(NODE_RADIUS_MAX, NODE_RADIUS_SCALE / max(n, 1)))


def compute_layout(graph_type: str, n: int, vertices: Sequence[int], edges: Sequence[Edge],
                   positions: Optional[LayoutDict] = None,
                   width: int = CANVAS_WIDTH, height: int = CANVAS_HEIGHT,
                   padding: int = CANVAS_PADDING,
                   timeout_ms: float = LAYOUT_TIMEOUT_MS) -> LayoutDict:
    if n == 0:
        return {}
    if positions:
        return layout_from_positions(positions, width, height, padding)
    if graph_type == 'PATH':
        return layout_path(n, edges, width, height, padding)
    if graph_type == 'TREE':
        return layout_tree(n, vertices, edges, width, height, padding, timeout_ms)
    if graph_type in ('BIPARTITE', 'COMPLETE_BIPARTITE'):
        return layout_two_columns(n, vertices, edges, width, height, padding)
    if graph_type in ('CYCLE', 'OUTERPLANAR'):
        return layout_circle(n, width, height, padding)
    if graph_type == 'WHEEL':
        return layout_wheel(n, width, height, padding)
    return layout_force_directed(n, vertices, edges, width, height, padding, timeout_ms)


def layout_from_positions(positions: LayoutDict, width: int, height: int, padding: int) -> LayoutDict:
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
    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2 - padding
    return {i: (cx + radius * math.cos(2 * math.pi * i / n - math.pi / 2),
                cy + radius * math.sin(2 * math.pi * i / n - math.pi / 2)) for i in range(n)}


def layout_wheel(n: int, width: int, height: int, padding: int) -> LayoutDict:
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
    return vertex_radius(n) + 5.0


def _segment_dist2(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    cx, cy = ax + t * dx - px, ay + t * dy - py
    return cx * cx + cy * cy


def edges_grazing_vertices(edges: Sequence[Edge], layout: LayoutDict, clearance: float) -> int:
    c2 = clearance * clearance
    count = 0
    for u, v in edges:
        (ax, ay), (bx, by) = layout[u], layout[v]
        for w, (px, py) in layout.items():
            if w != u and w != v and _segment_dist2(px, py, ax, ay, bx, by) < c2:
                count += 1
    return count


def _rooted(n: int, adj: List[List[int]], root: int):
    depth = [-1] * n
    depth[root] = 0
    children: List[List[int]] = [[] for _ in range(n)]
    order = [root]
    for v in order:
        for u in adj[v]:
            if depth[u] == -1:
                depth[u] = depth[v] + 1
                children[v].append(u)
                order.append(u)
    return depth, children, order


def _is_clean(n: int, edges: Sequence[Edge], layout: LayoutDict) -> bool:
    min_sep = 2.6 * vertex_radius(n)
    points = [layout[v] for v in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(points[i], points[j]) < min_sep:
                return False
    return (count_crossings(edges, layout) == 0
            and edges_grazing_vertices(edges, layout, edge_clearance(n)) == 0)


def _chain_order(n: int, edges: Sequence[Edge]) -> List[int]:
    adj = _adjacency(n, edges)
    start = next((v for v in range(n) if len(adj[v]) <= 1), 0)
    order, previous = [start], None
    while len(order) < n:
        following = [u for u in adj[order[-1]] if u != previous]
        if not following:
            break
        previous = order[-1]
        order.append(following[0])
    return order


def _winding_grid_path(cols: int, rows: int, rng, steps: int) -> List[Tuple[int, int]]:
    path = [(c if r % 2 == 0 else cols - 1 - c, r) for r in range(rows) for c in range(cols)]
    for _ in range(steps):
        if rng.random() < 0.5:
            path.reverse()
        (c, r), before = path[-1], path[-2] if len(path) > 1 else None
        options = [(c + dc, r + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= c + dc < cols and 0 <= r + dr < rows and (c + dc, r + dr) != before]
        if not options:
            continue
        cut = path.index(rng.choice(options))
        path[cut + 1:] = reversed(path[cut + 1:])
    return path


def layout_path(n: int, edges: Sequence[Edge], width: int, height: int, padding: int,
                rng=random) -> LayoutDict:
    if n == 1:
        return {0: (width / 2, height / 2)}
    chain = _chain_order(n, edges)
    scale = max(0.5, min(1.0, math.sqrt(n / 20)))
    w, h = (width - 2 * padding) * scale, (height - 2 * padding) * scale
    x0, y0 = (width - w) / 2, (height - h) / 2
    cols = max(2, math.ceil(math.sqrt(n * w / h)))
    rows = max(1, math.ceil(n / cols))

    layout: LayoutDict = {}
    for attempt in range(PATH_LAYOUT_ATTEMPTS):
        jitter = 0.2 if attempt < PATH_LAYOUT_ATTEMPTS - 1 else 0.0
        cells = _winding_grid_path(cols, rows, rng, 20 * cols * rows)[:n]
        xs = [c + rng.uniform(-jitter, jitter) for c, _ in cells]
        ys = [r + rng.uniform(-jitter, jitter) for _, r in cells]
        fx = _fit_axis(xs, x0, x0 + w)
        fy = _fit_axis(ys, y0, y0 + h)
        layout = {v: (fx(x), fy(y)) for v, x, y in zip(chain, xs, ys)}
        if _is_clean(n, edges, layout):
            break
    return layout


def layout_radial_tree(n: int, edges: Sequence[Edge], width: int, height: int, padding: int,
                       root: int, jitter: float, rng=random) -> LayoutDict:
    adj = _adjacency(n, edges)
    depth, children, order = _rooted(n, adj, root)
    leaves = [0] * n
    for v in reversed(order):
        leaves[v] = sum(leaves[c] for c in children[v]) or 1
    max_depth = max(depth) or 1

    start = rng.uniform(0, 2 * math.pi)
    span = {root: (start, start + 2 * math.pi)}
    angle = [0.0] * n
    radius = [0.0] * n
    for v in order:
        lo, hi = span[v]
        kids = list(children[v])
        rng.shuffle(kids)
        cursor = lo
        for c in kids:
            share = (hi - lo) * leaves[c] / leaves[v]
            span[c] = (cursor, cursor + share)
            angle[c] = cursor + share / 2 + rng.uniform(-jitter, jitter) * share / 2
            radius[c] = (depth[c] + rng.uniform(-jitter, jitter) / 2) / max_depth
            cursor += share

    cx, cy = width / 2, height / 2
    rx, ry = (width - 2 * padding) / 2, (height - 2 * padding) / 2
    return {v: (cx + rx * min(1.0, radius[v]) * math.cos(angle[v]),
                cy + ry * min(1.0, radius[v]) * math.sin(angle[v])) for v in range(n)}


def layout_tree(n: int, vertices: Sequence[int], edges: Sequence[Edge], width: int, height: int,
                padding: int, timeout_ms: float = LAYOUT_TIMEOUT_MS, rng=random) -> LayoutDict:
    if n == 1:
        return {0: (width / 2, height / 2)}
    for attempt in range(TREE_LAYOUT_ATTEMPTS):
        jitter = 0.6 if attempt < TREE_LAYOUT_ATTEMPTS * 2 // 3 else 0.2
        layout = layout_radial_tree(n, edges, width, height, padding, rng.randrange(n), jitter, rng)
        if _is_clean(n, edges, layout):
            return layout
    return layout_hierarchical_tree(n, vertices, edges, width, height, padding, timeout_ms)


def _bfs_farthest(start: int, adj: List[List[int]]):
    parent = {start: None}
    queue = deque([start])
    last = start
    while queue:
        last = queue.popleft()
        for v in adj[last]:
            if v not in parent:
                parent[v] = last
                queue.append(v)
    return last, parent


def layout_hierarchical_tree(n: int, vertices: Sequence[int], edges: Sequence[Edge],
                             width: int, height: int, padding: int,
                             timeout_ms: float = LAYOUT_TIMEOUT_MS) -> LayoutDict:
    adj = _adjacency(n, edges)
    a, _ = _bfs_farthest(0, adj)
    b, parent = _bfs_farthest(a, adj)
    path = [b]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    root = path[len(path) // 2]

    depth, children, order = _rooted(n, adj, root)
    if len(order) < n:
        return layout_force_directed(n, vertices, edges, width, height, padding, timeout_ms)

    slot = [0.0] * n
    next_slot = 0
    stack = [root]
    while stack:
        v = stack.pop()
        if not children[v]:
            slot[v] = next_slot
            next_slot += 1
        stack.extend(reversed(children[v]))
    for v in reversed(order):
        if children[v]:
            slot[v] = (slot[children[v][0]] + slot[children[v][-1]]) / 2

    max_depth = max(depth)
    fx = _fit_axis([0, max(next_slot - 1, 0)], padding, width - padding)
    level_gap = min(140.0, (height - 2 * padding) / max_depth) if max_depth else 0
    top = height / 2 - level_gap * max_depth / 2
    return {v: (fx(slot[v]) if next_slot > 1 else width / 2, top + depth[v] * level_gap)
            for v in range(n)}


def layout_force_directed(n: int, vertices: Sequence[int], edges: Sequence[Edge],
                          width: int, height: int, padding: int,
                          timeout_ms: float = LAYOUT_TIMEOUT_MS, rng=random) -> LayoutDict:
    start_time = time.perf_counter()
    if n == 1:
        return {0: (width / 2, height / 2)}

    iterations = 100 if n > 40 else 150 if n > 30 else 200
    w, h = width - 2 * padding, height - 2 * padding
    cx, cy = width / 2, height / 2
    k = 0.8 * math.sqrt(w * h / n)
    k2 = k * k

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
        for i in range(n):
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
        for u, v in edges:
            ddx, ddy = xs[u] - xs[v], ys[u] - ys[v]
            f = math.sqrt(ddx * ddx + ddy * ddy) / k
            dx[u] -= ddx * f
            dy[u] -= ddy * f
            dx[v] += ddx * f
            dy[v] += ddy * f
        for i in range(n):
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
