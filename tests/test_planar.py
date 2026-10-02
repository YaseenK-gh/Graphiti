from tests import support

import os
import random
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from algorithms.planar_puzzle import (Compactor, bridgeless, build_puzzle, conflicts, measure,
                                      puzzle_size)
from core.constants import PLANAR_MAX_N, PLANAR_MIN_N, PLANAR_RUN_SECONDS
from core.game_state import GameMode, GameScreen
from core.leaderboard import PlanarLeaderboard
from core.planar_run import PlanarRun
from ui.dialogs import HowToPlayDialog, LeaderboardDialog, PauseDialog
from ui.widgets.grid_paper import LayoutThumb
from ui.widgets.pixel import PixelButton
from tests.test_ui_flow import UITestCase, pump

SQUARE = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]


def fast_run(seed=1, clock=None):
    return PlanarRun(rng=random.Random(seed), clock=clock or (lambda: 0.0), search_seconds=0.01)


class TestPlanarGeometry(unittest.TestCase):
    def test_area_and_box_of_known_drawings(self):
        self.assertEqual(measure(4, SQUARE, [(1, 1), (4, 1), (4, 4), (1, 4)]), (9.0, 9))
        self.assertEqual(measure(4, SQUARE, [(2, 2), (3, 2), (3, 3), (2, 3)]), (1.0, 1))
        stretched = [(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)]
        self.assertEqual(measure(4, stretched, [(1, 3), (2, 3), (5, 2), (4, 2)]), (1.0, 4))

    def test_crossing_rules(self):
        self.assertEqual(conflicts([(0, 1), (2, 3)], [(0, 0), (2, 2), (0, 2), (2, 0)]), {0, 1})
        self.assertEqual(conflicts([(0, 1), (2, 3)], [(0, 0), (2, 0), (1, 0), (1, 3)]), {0, 1})
        self.assertEqual(conflicts([(0, 1), (0, 2)], [(0, 0), (2, 0), (1, 0)]), {0, 1})
        self.assertEqual(conflicts([(0, 1), (0, 2)], [(0, 0), (2, 0), (0, 2)]), set())


class TestPlanarPuzzles(unittest.TestCase):
    def test_every_puzzle_is_solvable_and_starts_tangled(self):
        rng = random.Random(5)
        for index in range(40):
            puzzle = build_puzzle(index % 16, rng)
            with self.subTest(index=index, n=puzzle.n):
                self.assertTrue(PLANAR_MIN_N <= puzzle.n <= PLANAR_MAX_N)
                self.assertEqual(conflicts(puzzle.edges, puzzle.solution), set())
                self.assertTrue(bridgeless(puzzle.n, puzzle.edges))
                self.assertTrue(conflicts(puzzle.edges, puzzle.start))
                for pos in (puzzle.start, puzzle.solution):
                    self.assertEqual(len(set(pos)), puzzle.n)
                    self.assertTrue(all(0 <= x <= puzzle.cols and 0 <= y <= puzzle.rows
                                        for x, y in pos))

    def test_sizes_grow_through_the_run(self):
        rng = random.Random(2)
        self.assertLessEqual(puzzle_size(0, rng)[0], PLANAR_MIN_N + 1)
        self.assertEqual(puzzle_size(40, rng)[0], PLANAR_MAX_N)
        self.assertLess(puzzle_size(0, rng)[1], puzzle_size(8, rng)[1])

    def test_search_never_makes_the_layout_worse_or_invalid(self):
        rng = random.Random(9)
        puzzle = build_puzzle(6, rng)
        search = Compactor(puzzle, rng)
        before = search.key
        for _ in range(400):
            search.step()
        self.assertLessEqual(search.key, before)
        self.assertEqual(conflicts(puzzle.edges, search.pos), set())
        self.assertEqual(search.key, measure(puzzle.n, puzzle.edges, search.pos))


class TestPlanarRun(unittest.TestCase):
    def test_submit_rules_and_totals(self):
        now = [0.0]
        run = fast_run(clock=lambda: now[0])
        run.start()
        first = run.current
        self.assertIsNone(run.submit(first.puzzle.start))
        now[0] = 20
        key = run.submit(first.puzzle.solution)
        self.assertEqual(key, measure(first.puzzle.n, first.puzzle.edges, first.puzzle.solution))
        self.assertEqual((run.solved, len(run.records)), (1, 2))
        self.assertEqual((run.total_area, run.total_box), key)
        self.assertEqual(run.rank_key(), (-1, key[0], key[1], 20))
        self.assertTrue(first.solved and not run.current.solved)

    def test_nothing_counts_after_time_is_up(self):
        now = [0.0]
        run = fast_run(clock=lambda: now[0])
        run.start()
        now[0] = PLANAR_RUN_SECONDS + 1
        self.assertTrue(run.time_up())
        self.assertIsNone(run.submit(run.current.puzzle.solution))
        self.assertEqual(run.solved, 0)

    def test_background_search_only_improves_the_program_layout(self):
        run = fast_run(seed=4)
        run.start()
        before = run.current.program_key
        run.improve(0.05)
        record = run.current
        self.assertLessEqual(record.program_key, before)
        self.assertEqual(record.program_key,
                         measure(record.puzzle.n, record.puzzle.edges, record.program_pos))


class TestPlanarLeaderboard(unittest.TestCase):
    def test_order_is_solved_then_area_then_box(self):
        path = os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), "planar.json")
        board = PlanarLeaderboard(path)
        board.add_entry("FEW", 2, 3.0, 4)
        board.add_entry("BIG", 5, 40.0, 60)
        board.add_entry("SMALL", 5, 22.5, 70)
        board.add_entry("TIDY", 5, 22.5, 30)
        self.assertEqual([e.player_name for e in board.get_top()], ["TIDY", "SMALL", "BIG", "FEW"])
        self.assertEqual([e.player_name for e in PlanarLeaderboard(path).get_top()],
                         ["TIDY", "SMALL", "BIG", "FEW"])


class TestPlanarFlow(UITestCase):
    def screen(self, which):
        return self.window.screens[which]

    def start(self, clock=None, seed=1):
        run = self.state.start_planar_run(fast_run(seed, clock))
        self.window.show_screen(GameScreen.PLANAR_PLAYING)
        pump()
        return run, self.screen(GameScreen.PLANAR_PLAYING)

    def test_mode_card_leads_to_a_run(self):
        self.window.show_screen(GameScreen.MODE_SELECT)
        self.screen(GameScreen.MODE_SELECT).planar_card.click()
        self.assertEqual(self.state.current_screen, GameScreen.PLANAR_INTRO)
        self.screen(GameScreen.PLANAR_INTRO).start_btn.click()
        self.assertEqual(self.state.current_screen, GameScreen.PLANAR_PLAYING)
        self.assertEqual(self.state.game_mode, GameMode.PLANAR)
        self.assertEqual(len(self.state.planar_run.records), 1)

    def test_vertices_slide_along_grid_lines_and_stop_at_taken_points(self):
        run, screen = self.start()
        paper = screen.paper
        puzzle = run.current.puzzle
        free = next((x, y) for x in range(puzzle.cols + 1) for y in range(puzzle.rows + 1)
                    if (x, y) not in paper.pos)
        seen = []
        paper.changed.connect(lambda: seen.append(tuple(paper.pos)))
        origin = paper.pos[0]
        QTest.mousePress(paper, Qt.MouseButton.LeftButton, pos=paper.point(origin).toPoint())
        QTest.mouseMove(paper, paper.point(free).toPoint())
        pump()
        QTest.mouseRelease(paper, Qt.MouseButton.LeftButton, pos=paper.point(free).toPoint())
        self.assertEqual(paper.pos[0], free)
        self.assertEqual(len(set(paper.pos)), puzzle.n)

        paper.selected = 0
        x, y = paper.pos[0]
        blocker = (x + 1, y) if x < puzzle.cols else (x - 1, y)
        key = Qt.Key.Key_Right if x < puzzle.cols else Qt.Key.Key_Left
        paper.pos[1] = blocker
        QTest.keyClick(paper, key)
        self.assertEqual(paper.pos[0], (x, y))
        paper.pos[1] = next(c for c in ((0, 0), (0, 1), (1, 0), (1, 1))
                            if c not in paper.pos and c != blocker)
        QTest.keyClick(paper, key)
        self.assertEqual(paper.pos[0], blocker)

    def test_slide_never_moves_diagonally(self):
        run, screen = self.start(seed=3)
        paper = screen.paper

        class Trail(list):
            moves = []

            def __setitem__(self, index, value):
                self.moves.append((self[index], value))
                super().__setitem__(index, value)

        paper.pos = Trail([(0, 0)] + [(10, i) for i in range(1, run.current.puzzle.n)])
        paper.selected = 0
        paper.slide((3, 2))
        self.assertEqual(paper.pos[0], (3, 2))
        self.assertEqual(len(Trail.moves), 5)
        for before, after in Trail.moves:
            self.assertEqual(abs(before[0] - after[0]) + abs(before[1] - after[1]), 1)

    def test_submit_only_when_planar_then_next_graph(self):
        run, screen = self.start()
        self.assertFalse(screen.submit_btn.isEnabled())
        QTest.keyClick(screen.paper, Qt.Key.Key_Return)
        self.assertEqual(run.solved, 0)
        self.assertIn("CROSSING", screen.message_label.text())

        first = run.current
        screen.paper.set_positions(first.puzzle.solution)
        self.assertTrue(screen.submit_btn.isEnabled())
        self.assertEqual(screen.state_badge.text(), "PLANAR")
        QTest.keyClick(screen.paper, Qt.Key.Key_Return)
        self.assertEqual((run.solved, len(run.records)), (1, 2))
        self.assertEqual(screen.paper.puzzle, run.current.puzzle)
        self.assertIn("GRAPH 2", screen.graph_label.text())
        self.assertIn("SOLVED: 1", screen.solved_label.text())

    def test_reset_returns_to_the_starting_tangle(self):
        run, screen = self.start()
        screen.paper.set_positions(run.current.puzzle.solution)
        QTest.keyClick(screen.paper, Qt.Key.Key_R)
        self.assertEqual(screen.paper.pos, run.current.puzzle.start)
        self.assertTrue(screen.paper.bad)

    def test_pause_has_no_forfeit_and_quit_discards_the_run(self):
        run, screen = self.start()
        dialog = screen.make_pause_dialog()
        labels = [b.text() for b in dialog.findChildren(PixelButton)]
        self.assertFalse(any("FORFEIT" in text for text in labels))
        self.assertTrue(any("QUIT" in text for text in labels))

        class FakePause:
            choice = PauseDialog.QUIT

            def exec(self):
                return 0

        screen.make_pause_dialog = lambda: FakePause()
        screen.confirm_quit = lambda: True
        screen.on_menu_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.MENU)
        self.assertIsNone(self.state.planar_run)

    def test_time_up_shows_both_layouts_for_every_graph(self):
        now = [0.0]
        run, screen = self.start(clock=lambda: now[0])
        first = run.current
        screen.paper.set_positions(first.puzzle.solution)
        screen.on_submit()
        now[0] = PLANAR_RUN_SECONDS - 30
        screen.tick()
        self.assertEqual(screen.timer_label.text(), "00:30")
        now[0] = PLANAR_RUN_SECONDS + 1
        screen.tick()
        self.assertEqual(self.state.current_screen, GameScreen.PLANAR_RESULTS)
        self.assertTrue(screen.paper.locked)

        results = self.screen(GameScreen.PLANAR_RESULTS)
        self.assertEqual(len(results.cards), 2)
        self.assertIn("SOLVED: 1", results.summary_label.text())
        texts = [label.text() for label in results.cards[0].findChildren(QLabel)]
        self.assertTrue(any(text.startswith("PROGRAM: AREA") for text in texts))
        self.assertTrue(any(text.startswith("YOU: AREA") for text in texts))
        thumbs = results.cards[0].findChildren(LayoutThumb)
        self.assertEqual([thumb.pos for thumb in thumbs], [first.program_pos, first.your_pos])
        unsolved = [label.text() for label in results.cards[1].findChildren(QLabel)]
        self.assertIn("YOU: NOT SOLVED", unsolved)
        self.assertIsNone(results.cards[1].findChildren(LayoutThumb)[1].pos)

    def test_score_goes_to_the_planar_leaderboard_once(self):
        now = [0.0]
        run, screen = self.start(clock=lambda: now[0])
        screen.paper.set_positions(run.current.puzzle.solution)
        screen.on_submit()
        now[0] = PLANAR_RUN_SECONDS + 1
        screen.tick()
        results = self.screen(GameScreen.PLANAR_RESULTS)
        before = len(self.state.planar_leaderboard.entries)
        results.name_input.setText("tester")
        results.on_submit_clicked()
        self.assertEqual(len(self.state.planar_leaderboard.entries), before + 1)
        self.assertFalse(results.submit_btn.isEnabled())
        self.assertEqual(self.state.submit_planar_score("tester")[1], "Score already submitted.")
        dialog = LeaderboardDialog(self.state.leaderboard_system, results,
                                   difficulty=LeaderboardDialog.PLANAR,
                                   planar=self.state.planar_leaderboard)
        table = dialog.tables[LeaderboardDialog.PLANAR]
        names = [table.item(row, 1).text() for row in range(table.rowCount())]
        self.assertIn("TESTER", names)

    def test_a_run_with_nothing_solved_cannot_be_submitted(self):
        now = [0.0]
        run, screen = self.start(clock=lambda: now[0])
        now[0] = PLANAR_RUN_SECONDS + 1
        screen.tick()
        results = self.screen(GameScreen.PLANAR_RESULTS)
        self.assertFalse(results.submit_btn.isEnabled())
        self.assertIsNotNone(self.state.submit_planar_score("tester")[1])

    def test_guide_explains_planar_drawing(self):
        text = HowToPlayDialog(self.screen(GameScreen.MENU)).text.text()
        self.assertIn("PLANAR DRAWING", text)
        self.assertIn("box", text)


if __name__ == "__main__":
    unittest.main()
