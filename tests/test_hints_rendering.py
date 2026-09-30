"""Phase 4: node/edge rendering spec and the hint system (core rules + UI)."""

from tests import support  # noqa: F401  (must be first)

import random
import unittest

from algorithms.coloring import detect_conflicts
from algorithms.solvers import build_adjacency_list, extend_coloring
from core.constants import (CONFLICT_EDGE_STROKE, DEFAULT_EDGE_STROKE, DEFAULT_NODE_FILL,
                            DEFAULT_NODE_STROKE, EDGE_CONFLICT_STROKE_WIDTH, EDGE_STROKE_WIDTH,
                            GRAPH_TYPES, NODE_STROKE_WIDTH, PALETTE)
from core.game_state import GameScreen, GameState
from core.graph_manager import GraphManager
from core.hint_system import HintSystem
from tests.test_ui_flow import UITestCase


class TestHintCore(unittest.TestCase):

    def test_costs(self):
        self.assertEqual(HintSystem.get_hint_cost('EASY'), 350)
        self.assertEqual(HintSystem.get_hint_cost('MEDIUM'), 700)
        self.assertEqual(HintSystem.get_hint_cost('HARD'), 1400)
        self.assertEqual(HintSystem.apply_hint_cost(1000, 'MEDIUM'), (300, True))
        self.assertEqual(HintSystem.apply_hint_cost(600, 'MEDIUM'), (600, False))
        self.assertFalse(HintSystem.can_buy_hint(1399, 'HARD'))

    def test_hints_are_always_extendable(self):
        """Following hints from any conflict-free partial coloring never creates a dead end."""
        rng = random.Random(3)
        for graph_type in GRAPH_TYPES:
            graph = GraphManager.generate_graph(graph_type, 20 if graph_type != 'NEAR_TRIANGULATION' else 18)
            adj = build_adjacency_list(graph.n, graph.edges)
            coloring = {v: None for v in graph.vertices}
            # Start from a random partial coloring taken from a valid solution.
            solution = extend_coloring(adj, graph.n, graph.chromatic_number)
            for v in rng.sample(graph.vertices, graph.n // 3):
                coloring[v] = solution[v]
            with self.subTest(type=graph_type):
                for _ in range(graph.n):
                    hint = HintSystem.get_hint_for_vertex(graph, coloring)
                    if hint is None:
                        break
                    v, c = hint
                    self.assertIsNone(coloring[v])
                    coloring[v] = c
                    self.assertFalse(detect_conflicts(coloring, graph.edges))
                self.assertTrue(all(c is not None for c in coloring.values()))
                self.assertIsNone(HintSystem.get_hint_for_vertex(graph, coloring))

    def test_hint_targets_conflict_when_fully_colored(self):
        graph = GraphManager.generate_graph('CYCLE', 6)
        coloring = {v: v % 2 for v in graph.vertices}
        coloring[0] = 1  # 0 now clashes with its neighbour(s) colored 1
        v, c = HintSystem.get_hint_for_vertex(graph, coloring)
        self.assertIn(v, {0, 1, 5})
        coloring[v] = c
        self.assertFalse(detect_conflicts(coloring, graph.edges))

    def make_state(self, points=5000):
        state = GameState()
        state.start_difficulty('EASY', ['PATH'])
        state.current_graph = GraphManager.generate_graph('PATH', 20)
        state.reset_for_new_graph()
        state.provisional_score = points
        return state

    def test_purchase_rules(self):
        state = self.make_state(points=5000)
        now = 1_000_000.0
        hint, err = state.buy_hint(now)
        self.assertIsNone(err)
        self.assertEqual(state.provisional_score, 4650)
        self.assertEqual(state.hints_used, 1)
        # Cooldown blocks spam clicks for 10s.
        hint, err = state.buy_hint(now + 3000)
        self.assertIsNone(hint)
        self.assertEqual(err, "Hint available in 7.0s")
        self.assertEqual(state.provisional_score, 4650)
        # Max 5 per level.
        for i in range(1, 5):
            _, err = state.buy_hint(now + i * 10_000)
            self.assertIsNone(err)
        _, err = state.buy_hint(now + 60_000)
        self.assertEqual(err, "No hints left for this level.")
        self.assertEqual(state.provisional_score, 5000 - 5 * 350)
        self.assertEqual(state.difficulty_hints_used, 5)

    def test_insufficient_points(self):
        state = self.make_state(points=349)
        hint, err = state.buy_hint(1.0)
        self.assertIsNone(hint)
        self.assertIn("Not enough points", err)
        self.assertEqual(state.provisional_score, 349)

    def test_reset_resets_count_but_not_points(self):
        """Doc example: 4000 → 2 hints (−700) → reset (−30%)."""
        state = self.make_state(points=4000)
        state.buy_hint(0.0)
        state.buy_hint(20_000.0)
        self.assertEqual(state.provisional_score, 3300)
        state.apply_level_reset()
        self.assertEqual(state.hints_used, 0)
        self.assertEqual(state.provisional_score, 2310)  # 3300 × 0.7, hint costs not refunded
        self.assertEqual(state.difficulty_hints_used, 2)

    def test_free_mode_hints_are_free(self):
        state = GameState()
        state.start_free_mode()
        state.current_graph = GraphManager.generate_graph('TREE', 15)
        state.reset_for_new_graph()
        hint, err = state.buy_hint(0.0)
        self.assertIsNone(err)
        self.assertEqual(state.provisional_score, 0)


class TestRenderingAndHintUI(UITestCase):

    def start_playing(self, graph_type='CYCLE', n=9):
        state = self.state
        state.start_difficulty('EASY', [graph_type, graph_type])
        state.current_graph = GraphManager.generate_graph(graph_type, n)
        self.window.show_screen(GameScreen.PLAYING)
        return self.screen(GameScreen.PLAYING)

    def test_default_rendering(self):
        canvas = self.start_playing().canvas
        for item in canvas.vertex_items.values():
            self.assertEqual(item.fill_color(), DEFAULT_NODE_FILL)
            self.assertEqual(item.pen().color().name().upper(), DEFAULT_NODE_STROKE)
            self.assertEqual(item.pen().widthF(), NODE_STROKE_WIDTH)
        for item in canvas.edge_items.values():
            self.assertEqual(item.pen().color().name().upper(), DEFAULT_EDGE_STROKE)
            self.assertEqual(item.pen().widthF(), EDGE_STROKE_WIDTH)
        # Straight line segments, drawn behind the vertices.
        self.assertTrue(all(e.zValue() < v.zValue() for e in canvas.edge_items.values()
                            for v in list(canvas.vertex_items.values())[:1]))

    def test_colored_and_conflict_rendering(self):
        canvas = self.start_playing().canvas
        canvas.color_vertex(0, 2)
        item = canvas.vertex_items[0]
        self.assertEqual(item.fill_color(), PALETTE[2])
        self.assertEqual(item.pen().color().name().upper(), DEFAULT_NODE_STROKE)
        canvas.color_vertex(1, 2)  # 0-1 is an edge of the cycle
        edge = canvas.edge_items["0-1"]
        self.assertEqual(edge.pen().color().name().upper(), CONFLICT_EDGE_STROKE)
        self.assertEqual(edge.pen().widthF(), EDGE_CONFLICT_STROKE_WIDTH)
        canvas.erase_vertex(1)
        self.assertEqual(edge.pen().color().name().upper(), DEFAULT_EDGE_STROKE)
        self.assertEqual(canvas.vertex_items[1].fill_color(), DEFAULT_NODE_FILL)

    def test_hint_button_flow(self):
        playing = self.start_playing()
        state = self.state
        state.provisional_score = 1000
        playing.update_hints_display()
        self.assertTrue(playing.hint_btn.isEnabled())
        self.assertIn("350", playing.hint_btn.text())

        playing.on_buy_hint()
        self.assertEqual(state.provisional_score, 650)
        self.assertEqual(playing.points_label.text(), "POINTS: 650")
        self.assertEqual(playing.hints_label.text(), "HINTS USED: 1/5")
        v, c = state.hints_available[-1]
        self.assertEqual(playing.canvas.hint_vertex, v)
        self.assertIsNotNone(playing.canvas._hint_halo)
        self.assertEqual(playing.canvas._hint_badge.color_index, c)
        self.assertEqual(playing.palette.suggested, c)
        self.assertIn("HINT", playing.message_label.text())

        # Cooldown: button disabled with a countdown, and a second press is refused.
        self.assertFalse(playing.hint_btn.isEnabled())
        self.assertIn("COOLDOWN", playing.hint_btn.text())
        playing.on_buy_hint()
        self.assertEqual(state.provisional_score, 650)
        self.assertIn("Hint available", playing.message_label.text())

        # Following the hint clears the highlight and causes no conflict.
        playing.canvas.color_vertex(v, c)
        self.assertIsNone(playing.canvas.hint_vertex)
        self.assertIsNone(playing.palette.suggested)
        self.assertFalse(playing.canvas.conflicts)

        # After the cooldown the second hint is affordable (650 ≥ 350); a third is not.
        state.hint_last_click_ms -= 10_000
        playing.on_buy_hint()
        self.assertEqual(state.provisional_score, 300)
        state.hint_last_click_ms -= 10_000
        playing.update_hints_display()
        self.assertFalse(playing.hint_btn.isEnabled())
        self.assertIn("Not enough points", playing.hint_btn.toolTip())

    def test_hint_key_shortcut(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        playing = self.start_playing()
        self.state.provisional_score = 400
        playing.canvas.setFocus()
        QTest.keyClick(playing.canvas, Qt.Key.Key_H)
        self.assertEqual(self.state.hints_used, 1)

    def test_free_mode_hint_label(self):
        state = self.state
        state.start_free_mode()
        state.current_graph = GraphManager.generate_graph('TREE', 12)
        self.window.show_screen(GameScreen.PLAYING)
        playing = self.screen(GameScreen.PLAYING)
        self.assertEqual(playing.hint_btn.text(), "FREE HINT (H)")
        self.assertTrue(playing.hint_btn.isEnabled())


if __name__ == '__main__':
    unittest.main()
