"""Phase 2: safe generation API, input validation and timeout recovery."""

from tests import support  # noqa: F401  (must be first)

import unittest
from unittest import mock

from core.graph_manager import GraphManager
from core.validation import validate_n


class TestValidateN(unittest.TestCase):

    def test_messages(self):
        cases = {
            "": "Please enter a number.",
            "   ": "Please enter a number.",
            "abc": "Please enter a valid integer.",
            "3.5": "Please enter a valid integer.",
            "0": "Number must be positive.",
            "-4": "Number must be positive.",
            "99999999999": "That number is far too large.",
            "61": "For PATH, n must be 2–60.",
            "1": "For PATH, n must be 2–60.",
        }
        for text, message in cases.items():
            with self.subTest(text=text):
                self.assertEqual(validate_n(text, 'PATH'), (None, message))

    def test_valid(self):
        self.assertEqual(validate_n(" 12 ", 'PATH'), (12, None))
        self.assertEqual(validate_n("25", 'COMPLETE_BIPARTITE'), (25, None))
        self.assertEqual(validate_n("26", 'COMPLETE_BIPARTITE')[0], None)

    def test_no_type(self):
        self.assertEqual(validate_n("10", None), (None, "Select a graph type first."))


class TestGenerateGraphSafe(unittest.TestCase):

    def test_success(self):
        graph, error = GraphManager.generate_graph_safe('PLANAR', 20)
        self.assertIsNone(error)
        self.assertEqual(graph.n, 20)

    def test_out_of_range(self):
        graph, error = GraphManager.generate_graph_safe('PLANAR', 46)
        self.assertIsNone(graph)
        self.assertIn("Must be between 5 and 45", error)

    def test_unknown_type(self):
        graph, error = GraphManager.generate_graph_safe('COMPLETE', 10)
        self.assertIsNone(graph)
        self.assertIn("Unknown graph type", error)

    def test_timeout_suggests_smaller_n(self):
        with mock.patch('core.graph_manager.GraphManager.generate_graph', side_effect=TimeoutError):
            with self.assertLogs('core.graph_manager', level='ERROR'):
                graph, error = GraphManager.generate_graph_safe('PLANAR', 30)
        self.assertIsNone(graph)
        self.assertIn("suggest 25", error)

    def test_generic_failure_is_caught(self):
        with mock.patch('core.graph_manager.generate_graph_full', side_effect=RuntimeError("kaboom")):
            with self.assertLogs('core.graph_manager', level='ERROR'):
                graph, error = GraphManager.generate_graph_safe('TREE', 10)
        self.assertIsNone(graph)
        self.assertIn("kaboom", error)

    def test_chromatic_timeout_still_produces_graph(self):
        """A solver timeout degrades to the 4-color fallback instead of failing generation."""
        with mock.patch('algorithms.solvers.CHROMATIC_TIMEOUT_MS', 0):
            import algorithms.solvers as solvers
            with mock.patch.object(solvers.compute_chromatic_number, '__defaults__', (0,)):
                graph, error = GraphManager.generate_graph_safe('NEAR_TRIANGULATION', 35)
        self.assertIsNone(error)
        self.assertIn(graph.chromatic_number, (3, 4))

    def test_suggested_lower_n_respects_minimum(self):
        self.assertEqual(GraphManager.suggested_lower_n('PLANAR', 7), 5)
        self.assertEqual(GraphManager.suggested_lower_n('PLANAR', 40), 35)


if __name__ == '__main__':
    unittest.main()
