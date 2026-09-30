"""STANDARD mode: each later level of a graph type needs a bigger n; max n locks in."""

from tests import support  # noqa: F401  (must be first)

import unittest

from core.constants import GRAPH_CONSTRAINTS
from core.game_state import GameScreen, GameState
from core.graph_manager import GraphManager
from core.validation import validate_n
from tests.test_ui_flow import UITestCase, wait_for_screen


class TestValidateWithPrevious(unittest.TestCase):

    def test_must_exceed_previous(self):
        self.assertEqual(validate_n("20", "PATH", prev_n=20)[0], None)
        self.assertIn("greater than 20", validate_n("20", "PATH", prev_n=20)[1])
        self.assertEqual(validate_n("21", "PATH", prev_n=20), (21, None))

    def test_locked_at_max(self):
        hi = GRAPH_CONSTRAINTS['PATH'][1]
        self.assertEqual(validate_n(str(hi), "PATH", prev_n=hi), (hi, None))
        self.assertIn("Locked", validate_n(str(hi - 1), "PATH", prev_n=hi)[1])

    def test_no_previous_is_unconstrained(self):
        self.assertEqual(validate_n("2", "PATH"), (2, None))


class TestStateRules(unittest.TestCase):

    def make_state(self):
        state = GameState()
        state.start_difficulty('EASY', ['PATH', 'CYCLE', 'PATH', 'PATH'])
        return state

    def test_per_type_tracking_and_lock(self):
        state = self.make_state()
        lo, hi = GRAPH_CONSTRAINTS['PATH']
        self.assertEqual(state.min_n_for('PATH'), lo)
        state.begin_graph(GraphManager.generate_graph('PATH', hi - 1))
        self.assertEqual(state.min_n_for('PATH'), hi)
        self.assertIsNone(state.locked_n_for('PATH'))
        self.assertEqual(state.min_n_for('CYCLE'), GRAPH_CONSTRAINTS['CYCLE'][0])  # Independent.
        state.begin_graph(GraphManager.generate_graph('PATH', hi))
        self.assertEqual(state.locked_n_for('PATH'), hi)
        self.assertEqual(state.min_n_for('PATH'), hi)

    def test_cleared_on_new_run_and_ignored_in_free_mode(self):
        state = self.make_state()
        state.begin_graph(GraphManager.generate_graph('PATH', 30))
        state.abandon_run()
        self.assertEqual(state.n_history, {})
        state.start_free_mode()
        state.begin_graph(GraphManager.generate_graph('PATH', 30))
        self.assertIsNone(state.previous_n_for('PATH'))


class TestPreGameScreen(UITestCase):

    def start_path_run(self):
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty('EASY')
        self.state.graph_queue = ['PATH', 'PATH', 'PATH'] + self.state.graph_queue[3:]
        self.window.show_screen(GameScreen.PRE_GAME)
        return self.screen(GameScreen.PRE_GAME)

    def finish_level(self, forfeit=False):
        playing = self.screen(GameScreen.PLAYING)
        if forfeit:
            playing.perform_forfeit()
        else:
            self.solve_current_graph()
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.screen(GameScreen.POST_LEVEL).on_next_clicked()

    def test_increasing_n_then_lock(self):
        pre = self.start_path_run()
        hi = GRAPH_CONSTRAINTS['PATH'][1]
        self.start_graph_from_pre_game(20)
        self.finish_level(forfeit=True)  # Forfeits still count.

        self.assertEqual(pre.n_input.text(), "21")  # Prefilled with the smallest allowed n.
        self.assertIn("n > 20", pre.rule_label.text())
        pre.n_input.setText("20")
        self.assertFalse(pre.start_btn.isEnabled())
        self.assertIn("greater than 20", pre.error_label.text())
        self.start_graph_from_pre_game(hi)
        self.finish_level()

        self.assertIn("LOCKED", pre.rule_label.text())
        self.assertTrue(pre.n_input.isReadOnly())
        self.assertEqual(pre.n_input.text(), str(hi))
        self.assertTrue(pre.start_btn.isEnabled())
        pre.on_start_clicked()
        self.assertEqual(self.state.current_graph.n, hi)

    def test_first_level_at_max_locks_the_type(self):
        pre = self.start_path_run()
        hi = GRAPH_CONSTRAINTS['PATH'][1]
        self.start_graph_from_pre_game(hi)
        self.finish_level()
        self.assertTrue(pre.n_input.isReadOnly())
        self.assertEqual(pre.n_input.text(), str(hi))


if __name__ == '__main__':
    unittest.main()
