"""Phase 1: every graph type generates valid, correctly-structured graphs across its n range."""

from tests import support  # noqa: F401  (must be first)

import random
import time
import unittest

from algorithms.generators import (GenerationError, generate_graph_by_type, generate_graph_full,
                                   is_connected)
from algorithms.geometry import count_crossings
from algorithms.solvers import (build_adjacency_list, compute_chromatic_number, extend_coloring,
                                has_triangle, is_bipartite, is_chordal, solve_chromatic)
from core.constants import GRAPH_CONSTRAINTS, GRAPH_TYPES
from core.graph_manager import GraphManager


def sample_ns(graph_type):
    lo, hi = GRAPH_CONSTRAINTS[graph_type]
    return sorted({lo, lo + 1, (lo + hi) // 2, hi - 1, hi})


class TestAllTypesGenerate(unittest.TestCase):

    def test_eleven_types_defined(self):
        self.assertEqual(len(GRAPH_TYPES), 11)
        self.assertNotIn('COMPLETE', GRAPH_TYPES)
        self.assertEqual(set(GRAPH_TYPES), set(GRAPH_CONSTRAINTS))

    def test_every_type_generates_valid_graphs(self):
        for graph_type in GRAPH_TYPES:
            for n in sample_ns(graph_type):
                for seed in range(3):
                    with self.subTest(type=graph_type, n=n, seed=seed):
                        vertices, edges = generate_graph_by_type(graph_type, n, rng=random.Random(seed))
                        self.assertEqual(vertices, list(range(n)))
                        self.assertEqual(len(edges), len(set(edges)), "duplicate edges")
                        for u, v in edges:
                            self.assertTrue(0 <= u < v < n, f"bad edge {(u, v)}")
                        self.assertTrue(is_connected(n, edges), "disconnected")

    def test_full_pipeline_every_type_at_max_n(self):
        """GraphManager builds a complete Graph (layout + χ) for every type at its max n."""
        for graph_type in GRAPH_TYPES:
            n = GRAPH_CONSTRAINTS[graph_type][1]
            with self.subTest(type=graph_type):
                start = time.perf_counter()
                graph = GraphManager.generate_graph(graph_type, n)
                elapsed = time.perf_counter() - start
                self.assertEqual(graph.n, n)
                self.assertEqual(set(graph.layout), set(range(n)))
                self.assertGreaterEqual(graph.chromatic_number, 2)
                self.assertLess(elapsed, 3.0, "generation too slow")

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            generate_graph_by_type('COMPLETE', 5)
        with self.assertRaises(ValueError):
            generate_graph_by_type('PATH', 61)
        with self.assertRaises(ValueError):
            generate_graph_by_type('PLANAR', 4)


class TestStructuralProperties(unittest.TestCase):

    def gen(self, graph_type, n, seed=0):
        return generate_graph_full(graph_type, n, rng=random.Random(seed))

    def test_path_cycle_wheel_exact_edges(self):
        _, e, _ = self.gen('PATH', 10)
        self.assertEqual(len(e), 9)
        degrees = [sum(v in edge for edge in e) for v in range(10)]
        self.assertEqual(sorted(degrees), [1, 1] + [2] * 8)  # One chain, two ends.
        _, e, _ = self.gen('CYCLE', 10)
        self.assertEqual(len(e), 10)
        _, e, _ = self.gen('WHEEL', 10)
        self.assertEqual(len(e), 18)  # 9 spokes + 9 rim

    def test_tree_is_tree(self):
        for n in sample_ns('TREE'):
            _, e, _ = self.gen('TREE', n, seed=n)
            self.assertEqual(len(e), n - 1)

    def test_bipartite_families(self):
        for t in ('BIPARTITE', 'COMPLETE_BIPARTITE'):
            for n in sample_ns(t):
                _, e, _ = self.gen(t, n, seed=n)
                a = n // 2
                for u, v in e:
                    self.assertTrue(u < a <= v, f"{t}: edge {(u, v)} inside a part")
        _, e, _ = self.gen('COMPLETE_BIPARTITE', 25)
        self.assertEqual(len(e), 12 * 13)

    def test_outerplanar_bounds(self):
        for n in sample_ns('OUTERPLANAR'):
            _, e, _ = self.gen('OUTERPLANAR', n, seed=n)
            self.assertLessEqual(len(e), 2 * n - 3)
            self.assertGreaterEqual(len(e), n)  # boundary cycle kept

    def test_chordal_is_chordal(self):
        for n in sample_ns('CHORDAL'):
            for seed in range(3):
                _, e, _ = self.gen('CHORDAL', n, seed=seed)
                self.assertTrue(is_chordal(build_adjacency_list(n, e), n))

    def test_planar_families_are_crossing_free(self):
        for t in ('TRIANGLE_FREE', 'NEAR_TRIANGULATION', 'PLANAR'):
            for n in sample_ns(t):
                _, e, pos = self.gen(t, n, seed=n)
                self.assertIsNotNone(pos)
                self.assertEqual(count_crossings(e, pos), 0, f"{t} n={n}")
                self.assertLessEqual(len(e), 3 * n - 6, f"{t} n={n} too many edges for planar")

    def test_triangle_free_has_no_triangles(self):
        for n in sample_ns('TRIANGLE_FREE'):
            for seed in range(3):
                _, e, _ = self.gen('TRIANGLE_FREE', n, seed=seed)
                self.assertFalse(has_triangle(build_adjacency_list(n, e), n))

    def test_near_triangulation_is_dense(self):
        for n in sample_ns('NEAR_TRIANGULATION'):
            _, e, _ = self.gen('NEAR_TRIANGULATION', n, seed=n)
            self.assertGreaterEqual(len(e), 2 * n - 3)

    def test_retry_logic_reraises_after_max_attempts(self):
        from algorithms import generators
        original = generators.GENERATORS['PATH']
        calls = []

        def broken(n, rng):
            calls.append(n)
            raise RuntimeError("boom")

        generators.GENERATORS['PATH'] = broken
        try:
            with self.assertLogs('algorithms.generators', level='WARNING'):
                with self.assertRaises(GenerationError):
                    generate_graph_by_type('PATH', 10, max_retries=3)
            self.assertEqual(len(calls), 3)
        finally:
            generators.GENERATORS['PATH'] = original

    def test_retry_recovers_from_transient_failure(self):
        from algorithms import generators
        original = generators.GENERATORS['PATH']
        attempts = []

        def flaky(n, rng):
            attempts.append(n)
            if len(attempts) == 1:
                raise RuntimeError("transient")
            return original(n, rng)

        generators.GENERATORS['PATH'] = flaky
        try:
            with self.assertLogs('algorithms.generators', level='WARNING'):
                _, e = generate_graph_by_type('PATH', 10)
            self.assertEqual(len(e), 9)
        finally:
            generators.GENERATORS['PATH'] = original


class TestChromaticNumbers(unittest.TestCase):
    """compute_chromatic_number agrees with an exact search for every type."""

    def test_closed_forms_and_solver_agree_with_exact_search(self):
        for graph_type in GRAPH_TYPES:
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            for n in sorted({lo, lo + 1, lo + 2, (lo + hi) // 2}):
                for seed in range(2):
                    with self.subTest(type=graph_type, n=n, seed=seed):
                        _, e = generate_graph_by_type(graph_type, n, rng=random.Random(seed))
                        chi = compute_chromatic_number(graph_type, n, e)
                        adj = build_adjacency_list(n, e)
                        exact, coloring, is_exact = solve_chromatic(adj, n, timeout_ms=None)
                        self.assertTrue(is_exact)
                        self.assertEqual(chi, exact)
                        self.assertIsNotNone(extend_coloring(adj, n, chi))
                        if chi > 1:
                            self.assertIsNone(extend_coloring(adj, n, chi - 1))

    def test_wheel_formula(self):
        # Rim of n-1 vertices: even rim → 3, odd rim → 4.
        self.assertEqual(compute_chromatic_number('WHEEL', 5, generate_graph_by_type('WHEEL', 5)[1]), 3)
        self.assertEqual(compute_chromatic_number('WHEEL', 6, generate_graph_by_type('WHEEL', 6)[1]), 4)

    def test_cycle_formula(self):
        self.assertEqual(compute_chromatic_number('CYCLE', 6, generate_graph_by_type('CYCLE', 6)[1]), 2)
        self.assertEqual(compute_chromatic_number('CYCLE', 7, generate_graph_by_type('CYCLE', 7)[1]), 3)

    def test_bipartite_types_really_bipartite(self):
        for t in ('PATH', 'TREE', 'BIPARTITE', 'COMPLETE_BIPARTITE'):
            n = GRAPH_CONSTRAINTS[t][1]
            _, e = generate_graph_by_type(t, n)
            self.assertTrue(is_bipartite(build_adjacency_list(n, e), n))


if __name__ == '__main__':
    unittest.main()
