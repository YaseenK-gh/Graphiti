"""Phase 5: badges, streaks, leaderboard persistence, and the end-of-difficulty UI."""

from tests import support  # noqa: F401  (must be first)

import json
import os
import tempfile
import unittest

from core.achievements import BADGE_INFO, AchievementSystem
from core.constants import COLORBLIND_SOLVES
from core.game_state import GameScreen
from core.leaderboard import LeaderboardSystem
from core.validation import validate_player_name
from tests.test_ui_flow import UITestCase


def temp_path(name):
    return os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), name)


class TestAchievements(unittest.TestCase):

    def test_perfect_speedrun_and_hint_master(self):
        a = AchievementSystem.load(temp_path("a.json"))
        new = a.on_difficulty_completed('EASY', resets=0, all_max_time=True, hints_used=0)
        self.assertEqual(set(new), {"perfect_easy", "speedrun_easy", "hint_master"})
        self.assertEqual(a.easy_streak, 1)
        # Earning again doesn't re-announce.
        self.assertEqual(a.on_difficulty_completed('EASY', 0, True, 0), [])
        self.assertEqual(a.easy_streak, 2)

    def test_every_difficulty_can_earn_perfect(self):
        a = AchievementSystem.load(temp_path("a.json"))
        for d in ('EASY', 'MEDIUM', 'HARD'):
            a.on_difficulty_completed(d, 0, False, 1)
        self.assertTrue({"perfect_easy", "perfect_medium", "perfect_hard"} <= a.badges_earned)
        self.assertNotIn("hint_master", a.badges_earned)

    def test_reset_or_forfeit_breaks_streak(self):
        a = AchievementSystem.load(temp_path("a.json"))
        a.on_difficulty_completed('HARD', 0, False, 2)
        a.on_difficulty_completed('HARD', 0, False, 2)
        self.assertEqual(a.hard_streak, 2)
        a.on_difficulty_completed('HARD', resets=1, all_max_time=False, hints_used=2)
        self.assertEqual(a.hard_streak, 0)
        a.on_difficulty_completed('HARD', 0, False, 0)
        a.on_difficulty_completed('HARD', 0, False, 0, forfeits=1)
        self.assertEqual(a.hard_streak, 0)
        self.assertEqual(a.easy_streak, 0)  # Streaks are per difficulty.

    def test_colorblind_after_50_solves(self):
        a = AchievementSystem.load(temp_path("a.json"))
        for i in range(COLORBLIND_SOLVES - 1):
            self.assertEqual(a.record_graph_solved(), [])
        self.assertEqual(a.record_graph_solved(), ["colorblind"])

    def test_persistence_roundtrip_and_corrupt_file(self):
        path = temp_path("a.json")
        a = AchievementSystem.load(path)
        a.on_difficulty_completed('MEDIUM', 0, True, 0)
        b = AchievementSystem.load(path)
        self.assertEqual(b.badges_earned, a.badges_earned)
        self.assertEqual(b.medium_streak, 1)
        with open(path, "w") as f:
            f.write("{not json")
        with self.assertLogs('core.storage', level='WARNING'):
            c = AchievementSystem.load(path)
        self.assertEqual(c.badges_earned, set())
        self.assertTrue(os.path.exists(path + ".corrupt"))

    def test_unknown_badges_ignored_on_load(self):
        path = temp_path("a.json")
        with open(path, "w") as f:
            json.dump({"badges_earned": ["hint_master", "hacked"], "easy_streak": -5}, f)
        a = AchievementSystem.load(path)
        self.assertEqual(a.badges_earned, {"hint_master"})
        self.assertEqual(a.easy_streak, 0)


class TestLeaderboard(unittest.TestCase):

    def test_sorting_ranks_and_persistence(self):
        path = temp_path("lb.json")
        lb = LeaderboardSystem(path)
        self.assertEqual(lb.add_entry("ANN", "EASY", 5000, 12), 1)
        self.assertEqual(lb.add_entry("BOB", "EASY", 9000, 12), 1)
        self.assertEqual(lb.add_entry("CY", "EASY", 5000, 11), 3)  # Tie: earlier entry ranks higher.
        self.assertEqual(lb.add_entry("DEE", "HARD", 100, 9), 1)
        top = lb.get_top_by_difficulty("EASY")
        self.assertEqual([e.player_name for e in top], ["BOB", "ANN", "CY"])
        reloaded = LeaderboardSystem(path)
        self.assertEqual([e.player_name for e in reloaded.get_top_by_difficulty("EASY")],
                         ["BOB", "ANN", "CY"])
        self.assertEqual(len(reloaded.get_top_by_difficulty("HARD")), 1)

    def test_cap_per_difficulty(self):
        lb = LeaderboardSystem(temp_path("lb.json"))
        lb.MAX_ENTRIES = 5
        for i in range(8):
            lb.add_entry(f"P{i}", "MEDIUM", i * 100, 12)
        lb.add_entry("H", "HARD", 1, 9)
        self.assertEqual(len(lb.get_top_by_difficulty("MEDIUM", 100)), 5)
        self.assertIsNone(lb.add_entry("LOW", "MEDIUM", 0, 12))  # Doesn't place.
        self.assertEqual(len(lb.get_top_by_difficulty("HARD")), 1)

    def test_malformed_rows_skipped(self):
        path = temp_path("lb.json")
        with open(path, "w") as f:
            json.dump([{"player_name": "OK", "difficulty": "EASY", "score": 10, "timestamp": 1,
                        "graph_count": 12},
                       {"player_name": "BAD"},
                       {"player_name": "X", "difficulty": "NOPE", "score": 1, "timestamp": 1,
                        "graph_count": 1}], f)
        lb = LeaderboardSystem(path)
        self.assertEqual([e.player_name for e in lb.entries], ["OK"])

    def test_name_validation(self):
        self.assertEqual(validate_player_name("  ada   lovelace "), ("ADA LOVELACE", None))
        self.assertEqual(validate_player_name(""), (None, "Please enter a name."))
        self.assertIn("at most", validate_player_name("x" * 17)[1])
        self.assertIn("only", validate_player_name("<script>")[1])


class TestEndOfDifficultyUI(UITestCase):

    def test_complete_easy_earns_badges_and_submits(self):
        self.play_difficulty('EASY')
        result = self.state.last_difficulty_result
        self.assertEqual(set(result.new_badges), {"perfect_easy", "speedrun_easy", "hint_master"})
        self.assertEqual(result.streak, 1)

        post = self.screen(GameScreen.POST_DIFFICULTY)
        self.assertIn("PERFECT NOVICE", post.badges_label.text())
        self.assertIn("EASY STREAK: 1", post.streak_label.text())

        post.name_input.setText("<bad>")
        post.on_submit_clicked()
        self.assertIn("only", post.name_error_label.text())
        self.assertEqual(self.state.leaderboard_system.entries, [])

        post.name_input.setText("tester")
        post.on_submit_clicked()
        self.assertEqual(post.name_error_label.text(), "SAVED — RANK #1")
        self.assertFalse(post.submit_btn.isEnabled())
        entry = self.state.leaderboard_system.get_top_by_difficulty('EASY')[0]
        self.assertEqual((entry.player_name, entry.score, entry.graph_count),
                         ("TESTER", result.banked_score, 12))
        # Second submission is refused.
        self.assertEqual(self.state.submit_score("again"), (None, "Score already submitted."))

        # Leaderboard and achievements dialogs render the data.
        from ui.dialogs import AchievementsDialog, LeaderboardDialog
        dialog = LeaderboardDialog(self.state.leaderboard_system, self.window, difficulty='EASY')
        self.assertEqual(dialog.tables['EASY'].item(0, 1).text(), "TESTER")
        self.assertIn("NO SCORES", dialog.tables['HARD'].item(0, 0).text())
        ach = AchievementsDialog(self.state.achievement_system, self.window)
        self.assertEqual(len(ach.badge_labels), len(BADGE_INFO))

    def test_reset_during_run_breaks_perfect_and_streak(self):
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty('HARD')
        self.start_graph_from_pre_game()
        self.screen(GameScreen.PLAYING).perform_reset()
        self.solve_current_graph()
        from tests.test_ui_flow import wait_for_screen
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.screen(GameScreen.POST_LEVEL).on_next_clicked()
        for _ in range(8):
            self.start_graph_from_pre_game()
            self.solve_current_graph()
            self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
            self.screen(GameScreen.POST_LEVEL).on_next_clicked()
        result = self.state.last_difficulty_result
        self.assertEqual(result.resets, 1)
        self.assertNotIn("perfect_hard", result.new_badges)
        self.assertIn("speedrun_hard", result.new_badges)
        self.assertEqual(result.streak, 0)

    def test_colorblind_badge_shown_after_level(self):
        self.state.achievement_system.graphs_solved = COLORBLIND_SOLVES - 1
        self.window.show_screen(GameScreen.DIFFICULTY_SELECT)
        self.screen(GameScreen.DIFFICULTY_SELECT).start_difficulty('EASY')
        self.start_graph_from_pre_game()
        self.solve_current_graph()
        from tests.test_ui_flow import wait_for_screen
        self.assertTrue(wait_for_screen(self.window, GameScreen.POST_LEVEL))
        self.assertIn("COLORBLIND", self.screen(GameScreen.POST_LEVEL).badges_label.text())


if __name__ == '__main__':
    unittest.main()
