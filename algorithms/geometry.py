"""Small computational-geometry helpers (pure Python, no NumPy/SciPy).

The planar graph families are built from a Delaunay triangulation of random
points. A Delaunay triangulation is a planar straight-line graph, so the point
coordinates double as a crossing-free drawing of the graph.
"""

import math
import random
from typing import Dict, List, Sequence, Set, Tuple

Point = Tuple[float, float]
Triangle = Tuple[int, int, int]


def random_points(n: int, rng=random, min_dist: float = None,
                  max_attempts: int = 40) -> List[Point]:
    """Well-spread random points in the unit square (Poisson-disc style rejection)."""
    if min_dist is None:
        min_dist = 0.6 / math.sqrt(max(n, 1))
    points: List[Point] = []
    while len(points) < n:
        min_d2 = min_dist * min_dist
        for _ in range(max_attempts):
            p = (rng.random(), rng.random())
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= min_d2 for q in points):
                points.append(p)
                break
        else:
            min_dist *= 0.9  # Too crowded: relax the spacing and keep going.
    return points


def _circumcircle(a: Point, b: Point, c: Point) -> Tuple[float, float, float]:
    """Return (center_x, center_y, radius²) of the circle through a, b, c."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-14:
        return 0.0, 0.0, math.inf  # Degenerate (collinear): contains everything.
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy, (ax - ux) ** 2 + (ay - uy) ** 2


def delaunay_triangles(points: Sequence[Point]) -> List[Triangle]:
    """Bowyer–Watson Delaunay triangulation. O(n²), fine for n ≤ ~100."""
    n = len(points)
    if n < 3:
        return []

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    mx = (max(xs) + min(xs)) / 2
    my = (max(ys) + min(ys)) / 2
    # Super-triangle comfortably enclosing every point.
    pts = list(points) + [
        (mx - 20 * span, my - 10 * span),
        (mx + 20 * span, my - 10 * span),
        (mx, my + 20 * span),
    ]

    circles: Dict[Triangle, Tuple[float, float, float]] = {}

    def circle(t: Triangle):
        c = circles.get(t)
        if c is None:
            c = circles[t] = _circumcircle(pts[t[0]], pts[t[1]], pts[t[2]])
        return c

    triangles: Set[Triangle] = {(n, n + 1, n + 2)}
    for i in range(n):
        px, py = pts[i]
        bad = []
        for t in triangles:
            cx, cy, r2 = circle(t)
            if (px - cx) ** 2 + (py - cy) ** 2 < r2:
                bad.append(t)

        # The cavity boundary is every edge used by exactly one bad triangle.
        edge_uses: Dict[Tuple[int, int], int] = {}
        for a, b, c in bad:
            for u, v in ((a, b), (b, c), (c, a)):
                key = (u, v) if u < v else (v, u)
                edge_uses[key] = edge_uses.get(key, 0) + 1
        for t in bad:
            triangles.discard(t)
            circles.pop(t, None)
        for (u, v), uses in edge_uses.items():
            if uses == 1:
                triangles.add((u, v, i))

    return [t for t in triangles if max(t) < n]


def delaunay_edges(points: Sequence[Point]) -> Set[Tuple[int, int]]:
    """Edge set (u < v) of the Delaunay triangulation of `points`."""
    n = len(points)
    if n == 2:
        return {(0, 1)}
    edges: Set[Tuple[int, int]] = set()
    for a, b, c in delaunay_triangles(points):
        for u, v in ((a, b), (b, c), (c, a)):
            edges.add((u, v) if u < v else (v, u))
    return edges


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """True if the open segments p1p2 and q1q2 properly intersect."""
    d1 = _orient(q1, q2, p1)
    d2 = _orient(q1, q2, p2)
    d3 = _orient(p1, p2, q1)
    d4 = _orient(p1, p2, q2)
    eps = 1e-12
    if min(abs(d1), abs(d2), abs(d3), abs(d4)) < eps:
        return False  # Touching / collinear: not a proper crossing.
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def count_crossings(edges: Sequence[Tuple[int, int]], positions: Dict[int, Point]) -> int:
    """Number of properly crossing edge pairs in a straight-line drawing."""
    crossings = 0
    edges = list(edges)
    for i in range(len(edges)):
        a, b = edges[i]
        pa, pb = positions[a], positions[b]
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            if a in (c, d) or b in (c, d):
                continue
            if segments_cross(pa, pb, positions[c], positions[d]):
                crossings += 1
    return crossings
