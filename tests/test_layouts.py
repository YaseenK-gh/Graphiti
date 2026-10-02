from tests import support

import math
import random
import time
import unittest

from algorithms.generators import generate_graph_by_type, generate_graph_full
from algorithms.geometry import count_crossings
from algorithms.layouts import (compute_layout, edges_grazing_vertices, layout_force_directed,
                                vertex_radius)
from core.constants import (CANVAS_HEIGHT, CANVAS_PADDING, CANVAS_WIDTH, GRAPH_CONSTRAINTS,
                            GRAPH_TYPES, LAYOUT_TIMEOUT_MS)

CROSSING_FREE = {'PATH', 'TREE', 'CYCLE', 'WHEEL', 'OUTERPLANAR', 'TRIANGLE_FREE',
                 'NEAR_TRIANGULATION', 'PLANAR'}


def min_pair_distance(layout):
    pts = list(layout.values())
    return min(math.dist(pts[i], pts[j]) for i in range(len(pts)) for j in range(i + 1, len(pts)))


class TestLayouts(unittest.TestCase):
    def test_all_types_in_bounds_no_overlap(self):
        for graph_type in GRAPH_TYPES:
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            for n in (lo, (lo + hi) // 2, hi):
                with self.subTest(type=graph_type, n=n):
                    vertices, edges, positions = generate_graph_full(graph_type, n, rng=random.Random(n))
                    layout = compute_layout(graph_type, n, vertices, edges, positions)
                    self.assertEqual(set(layout), set(range(n)))
                    for x, y in layout.values():
                        self.assertTrue(CANVAS_PADDING - 1e-6 <= x <= CANVAS_WIDTH - CANVAS_PADDING + 1e-6)
                        self.assertTrue(CANVAS_PADDING - 1e-6 <= y <= CANVAS_HEIGHT - CANVAS_PADDING + 1e-6)
                    self.assertGreaterEqual(min_pair_distance(layout), 2 * vertex_radius(n) - 1e-6)

    def test_crossing_free_families(self):
        for graph_type in CROSSING_FREE:
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            for n in (lo, (lo + hi) // 2, hi):
                for seed in range(2):
                    with self.subTest(type=graph_type, n=n, seed=seed):
                        v, e, pos = generate_graph_full(graph_type, n, rng=random.Random(seed))
                        layout = compute_layout(graph_type, n, v, e, pos)
                        self.assertEqual(count_crossings(e, layout), 0)

    def test_paths_and_trees_never_cross_or_touch_other_vertices(self):
        for graph_type in ('PATH', 'TREE'):
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            for n in (lo, 10, (lo + hi) // 2, hi):
                for seed in range(12):
                    with self.subTest(type=graph_type, n=n, seed=seed):
                        random.seed(seed)
                        v, e, pos = generate_graph_full(graph_type, n, rng=random.Random(seed))
                        start = time.perf_counter()
                        layout = compute_layout(graph_type, n, v, e, pos)
                        self.assertLess((time.perf_counter() - start) * 1000, LAYOUT_TIMEOUT_MS)
                        self.assertEqual(count_crossings(e, layout), 0)
                        self.assertEqual(edges_grazing_vertices(e, layout, vertex_radius(n)), 0)

    def test_paths_wind_instead_of_running_straight(self):
        v, e, pos = generate_graph_full('PATH', 40, rng=random.Random(2))
        random.seed(2)
        layout = compute_layout('PATH', 40, v, e, pos)
        self.assertGreater(len({round(y) for _, y in layout.values()}), 3)
        self.assertGreater(len({round(x) for x, _ in layout.values()}), 3)

    def test_path_labels_are_shuffled(self):
        _, e, _ = generate_graph_full('PATH', 30, rng=random.Random(1))
        self.assertNotEqual(sorted(e), [(i, i + 1) for i in range(29)])

    def test_force_directed_respects_timeout(self):
        v, e = generate_graph_by_type('CHORDAL', 40)
        start = time.perf_counter()
        layout = layout_force_directed(40, v, e, CANVAS_WIDTH, CANVAS_HEIGHT, CANVAS_PADDING)
        self.assertLess((time.perf_counter() - start) * 1000, LAYOUT_TIMEOUT_MS)
        self.assertEqual(len(layout), 40)

    def test_force_directed_stops_on_tiny_timeout(self):
        v, e = generate_graph_by_type('PLANAR', 45)
        start = time.perf_counter()
        with self.assertLogs('algorithms.layouts', level='WARNING'):
            layout = layout_force_directed(45, v, e, CANVAS_WIDTH, CANVAS_HEIGHT, CANVAS_PADDING,
                                           timeout_ms=1)
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertEqual(len(layout), 45)

    def test_vertex_radius_clamp(self):
        self.assertEqual(vertex_radius(10), 14)
        self.assertEqual(vertex_radius(30), 10)
        self.assertEqual(vertex_radius(60), 8)


if __name__ == '__main__':
    unittest.main()
