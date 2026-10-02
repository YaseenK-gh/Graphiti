from tests import support

import time
import unittest

from algorithms.coloring import count_distinct_colors, detect_conflicts, greedy_solve, is_graph_colored
from algorithms.solvers import (backtrack_chromatic_number, build_adjacency_list, chordal_clique_number,
                                extend_coloring, find_max_clique_size, is_chordal, optimal_coloring,
                                solve_chromatic)


def complete(n):
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


PETERSEN = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
            (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
            (5, 7), (7, 9), (9, 6), (6, 8), (8, 5)]


class TestSolvers(unittest.TestCase):
    def chi(self, n, edges):
        k, coloring, exact = solve_chromatic(build_adjacency_list(n, edges), n, timeout_ms=None)
        self.assertTrue(exact)
        self.assertFalse(detect_conflicts(dict(enumerate(coloring)), edges))
        return k

    def test_known_values(self):
        self.assertEqual(self.chi(4, complete(4)), 4)
        self.assertEqual(self.chi(5, complete(5)), 5)
        self.assertEqual(self.chi(5, [(i, (i + 1) % 5) for i in range(5)]), 3)
        self.assertEqual(self.chi(10, PETERSEN), 3)
        self.assertEqual(self.chi(3, []), 1)

    def test_max_clique(self):
        self.assertEqual(find_max_clique_size(build_adjacency_list(10, PETERSEN), 10), 2)
        edges = complete(4) + [(3, 4), (4, 5)]
        self.assertEqual(find_max_clique_size(build_adjacency_list(6, edges), 6), 4)

    def test_chordal(self):
        c4 = [(0, 1), (1, 2), (2, 3), (3, 0)]
        self.assertFalse(is_chordal(build_adjacency_list(4, c4), 4))
        c4_chord = c4 + [(0, 2)]
        adj = build_adjacency_list(4, c4_chord)
        self.assertTrue(is_chordal(adj, 4))
        self.assertEqual(chordal_clique_number(adj, 4), 3)

    def test_extend_coloring_respects_precoloring(self):
        edges = [(0, 1), (1, 2), (2, 0), (2, 3)]
        adj = build_adjacency_list(4, edges)
        result = extend_coloring(adj, 4, max_colors=3, precolored={0: 7, 1: 2}, palette_size=10)
        self.assertEqual(result[0], 7)
        self.assertEqual(result[1], 2)
        self.assertNotIn(result[2], (7, 2))
        self.assertIsNone(extend_coloring(adj, 4, 3, precolored={0: 1, 1: 1}, palette_size=10))

    def test_timeout_falls_back_quickly(self):
        n = 40
        edges = complete(8) + [(i, i + 1) for i in range(7, n - 1)]
        adj = build_adjacency_list(n, edges)
        start = time.perf_counter()
        k, coloring, _ = solve_chromatic(adj, n, timeout_ms=0)
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertGreaterEqual(k, 8)
        self.assertFalse(detect_conflicts(dict(enumerate(coloring)), edges))

    def test_backtrack_fallback_is_capped_at_four(self):
        edges = PETERSEN
        k = backtrack_chromatic_number(build_adjacency_list(10, edges), 10, timeout_ms=10_000)
        self.assertEqual(k, 3)

    def test_optimal_coloring_uses_chi_colors(self):
        coloring = optimal_coloring(10, PETERSEN, chromatic_number=3)
        self.assertEqual(count_distinct_colors(coloring), 3)
        self.assertFalse(detect_conflicts(coloring, PETERSEN))

    def test_greedy_solve_and_helpers(self):
        coloring = greedy_solve(PETERSEN, 10)
        self.assertTrue(is_graph_colored(coloring, 10))
        self.assertFalse(detect_conflicts(coloring, PETERSEN))
        self.assertFalse(is_graph_colored({0: 1, 1: None}, 2))


if __name__ == '__main__':
    unittest.main()
