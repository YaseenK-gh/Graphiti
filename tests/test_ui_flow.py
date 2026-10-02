from tests import support

import os
import tempfile
import time
import unittest

from PySide6.QtCore import Qt

from algorithms.solvers import optimal_coloring
from core.achievements import AchievementSystem
from core.leaderboard import LeaderboardSystem
from core.constants import DIFFICULTY_CONFIG, GRAPH_CONSTRAINTS
from core.game_state import GameMode, GameScreen, GameState


def pump(ms=0):
    app = support.qapp()
    end = time.perf_counter() + ms / 1000
    app.processEvents()
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.005)


def wait_for_screen(window, screen, timeout_ms=5000):
    end = time.perf_counter() + timeout_ms / 1000
    while window.game_state.current_screen != screen and time.perf_counter() < end:
        pump(10)
    return window.game_state.current_screen == screen


class UITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.qapp()
        from ui.main_window import MainWindow
        cls.MainWindow = MainWindow

    def setUp(self):
        self.data_dir = tempfile.mkdtemp(dir=support.TEST_DATA_DIR)
        state = GameState(
            achievement_system=AchievementSystem.load(os.path.join(self.data_dir, "achievements.json")),
            leaderboard_system=LeaderboardSystem(os.path.join(self.data_dir, "leaderboard.json")))
        self.window = self.MainWindow(state)
        self.window.resize(1400, 820)
        self.window.show()
        playing = self.window.screens[GameScreen.PLAYING]
        playing.completion_delay_ms = 0
        playing.forfeit_linger_ms = 0
        pump()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        pump()

    @property
    def state(self):
        return self.window.game_state

    def screen(self, which):
        return self.window.screens[which]

    def solve_current_graph(self):
        graph = self.state.current_graph
        canvas = self.screen(GameScreen.PLAYING).canvas
        for v, c in optimal_coloring(graph.n, graph.edges, graph.chromatic_number).items():
            canvas.color_vertex(v, c)

    def start_graph_from_pre_game(self, n=None):
        pre = self.screen(GameScreen.PRE_GAME)
        graph_type = pre.selected_graph_type
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        if n is None:
            n = max(min(hi, lo + 8), self.state.min_n_for(graph_type))
        pre.n_input.setText(str(n))
        self.assertTrue(pre.start_btn.isEnabled())
        pre.on_start_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.PLAYING)

    def play_difficulty(self, difficulty):
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty(difficulty)
        config = DIFFICULTY_CONFIG[difficulty]
        self.assertEqual(len(self.state.graph_queue), config['num_graphs'])
        self.assertEqual(sorted(set(self.state.graph_queue)), sorted(config['graph_types']))
        for i in range(config['num_graphs']):
            self.assertEqual(self.state.current_screen, GameScreen.PRE_GAME, f"graph {i}")
            self.start_graph_from_pre_game()
            self.assertEqual(self.state.current_graph.type, self.state.graph_queue[i])
            self.solve_current_graph()
            self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
            self.assertFalse(self.state.last_level_result.forfeited)
            self.screen(GameScreen.POST_LEVEL).on_next_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.POST_DIFFICULTY)
        return self.state.last_difficulty_result


class TestFullRuns(UITestCase):
    def check_run(self, difficulty):
        result = self.play_difficulty(difficulty)
        num = DIFFICULTY_CONFIG[difficulty]['num_graphs']
        self.assertEqual(len(self.state.level_results), num)
        self.assertTrue(all(r.colors_used <= r.chromatic_number for r in self.state.level_results))
        self.assertTrue(result.all_max_time)
        self.assertEqual(result.banked_score, result.provisional_score * 5)
        self.assertEqual(result.provisional_score, sum(self.state.level_scores))
        post = self.screen(GameScreen.POST_DIFFICULTY)
        self.assertEqual(post.title_label.text(), DIFFICULTY_CONFIG[difficulty]['title'])

    def test_easy_run(self):
        self.check_run('EASY')

    def test_medium_run(self):
        self.check_run('MEDIUM')

    def test_hard_run(self):
        self.check_run('HARD')

    def test_next_difficulty_button(self):
        self.play_difficulty('EASY')
        self.screen(GameScreen.POST_DIFFICULTY).on_next_difficulty_clicked()
        self.assertEqual(self.state.difficulty, 'MEDIUM')
        self.assertEqual(self.state.current_screen, GameScreen.PRE_GAME)
        self.assertEqual(self.state.provisional_score, 0)


class TestPlayingScreen(UITestCase):
    def start_easy(self):
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty('EASY')
        self.start_graph_from_pre_game()
        return self.screen(GameScreen.PLAYING)

    def test_invalid_n_disables_start(self):
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty('HARD')
        pre = self.screen(GameScreen.PRE_GAME)
        for bad in ("", "abc", "0", "999"):
            pre.n_input.setText(bad)
            self.assertFalse(pre.start_btn.isEnabled(), bad)
            self.assertTrue(pre.error_label.text())
        pre.on_start_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.PRE_GAME)

    def test_conflicts_and_right_click_erase(self):
        playing = self.start_easy()
        canvas = playing.canvas
        u, v = self.state.current_graph.edges[0]
        canvas.color_vertex(u, 0)
        canvas.color_vertex(v, 0)
        self.assertIn(f"{min(u, v)}-{max(u, v)}", canvas.conflicts)
        self.assertIn("CONFLICT", playing.conflict_label.text())
        from PySide6.QtTest import QTest
        pos = canvas.mapFromScene(canvas.vertex_items[v].pos())
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, pos)
        self.assertIsNone(canvas.coloring[v])
        self.assertFalse(canvas.conflicts)
        playing.on_color_selected(4)
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        self.assertEqual(canvas.coloring[v], 4)
        self.assertIs(self.state.coloring, canvas.coloring)

    def test_keyboard_shortcuts_pick_colors(self):
        from PySide6.QtTest import QTest
        playing = self.start_easy()
        playing.canvas.setFocus()
        pump()
        QTest.keyClick(playing.canvas, Qt.Key.Key_3)
        self.assertEqual(playing.canvas.active_color, 2)
        QTest.keyClick(playing.canvas, Qt.Key.Key_0)
        self.assertEqual(playing.canvas.active_color, 9)

    def test_reset_applies_penalty(self):
        playing = self.start_easy()
        self.state.provisional_score = 1000
        playing.canvas.color_vertex(0, 1)
        lost = playing.perform_reset()
        self.assertEqual(lost, 300)
        self.assertEqual(self.state.provisional_score, 700)
        self.assertEqual(playing.canvas.colored_count(), 0)
        self.assertEqual(self.state.resets, 1)

    def test_forfeit_reveals_solution_and_scores_zero(self):
        playing = self.start_easy()
        playing.perform_forfeit()
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.assertTrue(self.state.last_level_result.forfeited)
        self.assertEqual(self.state.last_level_result.score, 0)
        self.assertTrue(playing.canvas.is_complete())

    def test_timer_runs_and_stops(self):
        playing = self.start_easy()
        self.state.timer_start -= 65
        self.window.update_game()
        self.assertEqual(playing.timer_label.text(), "01:05")
        self.solve_current_graph()
        self.assertFalse(self.state.timer_running)

    def test_timer_keeps_running_while_paused(self):
        playing = self.start_easy()
        state = self.state

        class FakePauseDialog:
            choice = "resume"

            def exec(self):
                state.timer_start -= 10
                return 0

        playing.make_pause_dialog = lambda: FakePauseDialog()
        playing.on_menu_clicked()
        self.assertTrue(state.timer_running)
        self.assertGreaterEqual(state.get_elapsed_seconds(), 10)

    def test_forfeit_offers_main_menu(self):
        playing = self.start_easy()
        post = self.screen(GameScreen.POST_LEVEL)
        playing.perform_forfeit()
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.assertFalse(post.menu_btn.isHidden())
        post.confirm_abandon = lambda: False
        post.on_menu_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.POST_LEVEL)
        post.confirm_abandon = lambda: True
        post.on_menu_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.MENU)
        self.assertEqual(self.state.graph_queue, [])
        self.assertEqual(self.state.n_history, {})

    def test_no_menu_button_after_normal_completion(self):
        self.start_easy()
        self.solve_current_graph()
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.assertTrue(self.screen(GameScreen.POST_LEVEL).menu_btn.isHidden())

    def test_abandon_restarts_difficulty(self):
        self.start_easy()
        self.state.abandon_run()
        self.window.show_screen(GameScreen.MENU)
        self.assertEqual(self.state.graph_queue, [])
        self.assertEqual(self.state.provisional_score, 0)


class TestFreeMode(UITestCase):
    def test_every_type_playable_in_free_mode(self):
        select = self.screen(GameScreen.FREE_GRAPH_SELECT)
        for graph_type, (lo, hi) in GRAPH_CONSTRAINTS.items():
            with self.subTest(type=graph_type):
                self.window.show_screen(GameScreen.FREE_GRAPH_SELECT)
                select.select_type(graph_type)
                select.n_widget.n_input.setText(str(hi))
                select.on_start_clicked()
                self.assertEqual(self.state.current_screen, GameScreen.PLAYING)
                self.assertEqual(self.state.game_mode, GameMode.FREE)
                self.assertEqual(self.state.current_graph.n, hi)
                self.solve_current_graph()
                self.assertTrue(wait_for_screen(self.window, GameScreen.FREE_COMPLETE))
                done = self.screen(GameScreen.FREE_COMPLETE)
                self.assertIn("OPTIMAL", done.verdict_label.text())

    def test_play_again_keeps_type_and_n(self):
        select = self.screen(GameScreen.FREE_GRAPH_SELECT)
        self.window.show_screen(GameScreen.FREE_GRAPH_SELECT)
        select.select_type('WHEEL')
        select.n_widget.n_input.setText("12")
        select.on_start_clicked()
        self.solve_current_graph()
        self.assertTrue(wait_for_screen(self.window, GameScreen.FREE_COMPLETE))
        self.screen(GameScreen.FREE_COMPLETE).on_play_again_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.PLAYING)
        self.assertEqual((self.state.current_graph.type, self.state.current_graph.n), ('WHEEL', 12))


if __name__ == '__main__':
    unittest.main()
