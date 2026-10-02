from tests import support

import unittest

from core.game_state import GameMode, GameState, Graph
from core.scoring import ScoringSystem


def tiny_graph(chi=2, n=10, graph_type='PATH'):
    return Graph(type=graph_type, n=n, vertices=list(range(n)),
                 edges=[(i, i + 1) for i in range(n - 1)], chromatic_number=chi)


class TestScoring(unittest.TestCase):
    def test_time_bonus_tiers(self):
        self.assertEqual(ScoringSystem._get_time_bonus('EASY', 10), 1000)
        self.assertEqual(ScoringSystem._get_time_bonus('EASY', 45), 500)
        self.assertEqual(ScoringSystem._get_time_bonus('EASY', 89), 200)
        self.assertEqual(ScoringSystem._get_time_bonus('EASY', 500), 0)

    def test_medium_tiers_sorted_numerically(self):
        self.assertEqual(ScoringSystem._get_time_bonus('MEDIUM', 30), 1500)
        self.assertEqual(ScoringSystem._get_time_bonus('MEDIUM', 90), 800)
        self.assertEqual(ScoringSystem._get_time_bonus('MEDIUM', 150), 300)
        self.assertEqual(ScoringSystem._get_time_bonus('MEDIUM', 181), 0)
        self.assertEqual(ScoringSystem.max_time_threshold('MEDIUM'), 60)

    def test_hard_tiers(self):
        self.assertEqual(ScoringSystem._get_time_bonus('HARD', 119), 2500)
        self.assertEqual(ScoringSystem._get_time_bonus('HARD', 200), 1500)
        self.assertEqual(ScoringSystem._get_time_bonus('HARD', 299), 500)
        self.assertEqual(ScoringSystem._get_time_bonus('HARD', 301), 0)

    def test_level_score(self):
        self.assertEqual(ScoringSystem.compute_level_score('EASY', 10, 20, 2, 2), 2100)
        self.assertEqual(ScoringSystem.compute_level_score('EASY', 10, 20, 3, 2), 1800)
        self.assertEqual(ScoringSystem.compute_level_score('EASY', 10, 20, 4, 2), 1600)
        self.assertEqual(ScoringSystem.compute_level_score('HARD', 250, 30, 4, 4), 4600)

    def test_optimality_when_player_beats_fallback_chi(self):
        self.assertEqual(ScoringSystem._get_optimality_bonus(3, 4), 500)

    def test_penalty_and_multiplier(self):
        self.assertEqual(ScoringSystem.apply_reset_penalty(3800, 'HARD'), 2660)
        self.assertEqual(ScoringSystem.apply_500_percent_bonus(7330, True), 36650)
        self.assertEqual(ScoringSystem.apply_500_percent_bonus(7330, False), 7330)
        self.assertTrue(ScoringSystem.check_max_time_bonus(29.9, 'EASY'))
        self.assertFalse(ScoringSystem.check_max_time_bonus(30, 'EASY'))


class TestGameStateRun(unittest.TestCase):
    def make_state(self):
        state = GameState()
        state.start_difficulty('EASY', ['PATH', 'CYCLE'])
        state.current_graph = tiny_graph()
        state.reset_for_new_graph()
        return state

    def test_level_completion_accumulates(self):
        state = self.make_state()
        result = state.record_level_completion(colors_used=2)
        self.assertEqual(result.score, 500 + 1000 + 50 + 500)
        self.assertTrue(result.max_time_bonus)
        self.assertEqual(state.provisional_score, 2050)
        self.assertEqual(state.max_time_bonus_hits, 1)

    def test_reset_penalty_and_clear(self):
        state = self.make_state()
        state.provisional_score = 4000
        state.coloring[0] = 3
        lost = state.apply_level_reset()
        self.assertEqual(lost, 1200)
        self.assertEqual(state.provisional_score, 2800)
        self.assertEqual(state.resets, 1)
        self.assertIsNone(state.coloring[0])

    def test_free_mode_reset_is_free(self):
        state = GameState()
        state.start_free_mode()
        state.current_graph = tiny_graph()
        state.reset_for_new_graph()
        self.assertEqual(state.apply_level_reset(), 0)
        self.assertEqual(state.resets, 0)
        self.assertEqual(state.game_mode, GameMode.FREE)

    def test_forfeit_scores_zero_and_breaks_multiplier(self):
        state = self.make_state()
        state.record_level_completion(colors_used=2)
        state.advance_to_next_graph()
        state.current_graph = tiny_graph()
        state.reset_for_new_graph()
        forfeit = state.record_level_completion(colors_used=2, forfeited=True)
        self.assertEqual(forfeit.score, 0)
        self.assertEqual(state.forfeits, 1)
        result = state.finalize_difficulty()
        self.assertFalse(result.all_max_time)
        self.assertEqual(result.banked_score, 2050)
        self.assertEqual(result.graphs_completed, 1)

    def test_all_max_time_multiplies(self):
        state = self.make_state()
        state.record_level_completion(colors_used=2)
        state.advance_to_next_graph()
        state.current_graph = tiny_graph()
        state.reset_for_new_graph()
        state.record_level_completion(colors_used=2)
        result = state.finalize_difficulty()
        self.assertTrue(result.all_max_time)
        self.assertEqual(result.banked_score, 4100 * 5)
        self.assertEqual(state.total_banked, 20500)

    def test_timer_pause_resume(self):
        state = self.make_state()
        state.timer_start -= 5
        state.pause_timer()
        paused_at = state.get_elapsed_seconds()
        self.assertAlmostEqual(paused_at, 5, delta=0.1)
        self.assertEqual(state.get_elapsed_seconds(), paused_at)
        state.resume_timer()
        self.assertGreaterEqual(state.get_elapsed_seconds(), paused_at)

    def test_next_difficulty(self):
        self.assertEqual(GameState.next_difficulty('EASY'), 'MEDIUM')
        self.assertEqual(GameState.next_difficulty('MEDIUM'), 'HARD')
        self.assertIsNone(GameState.next_difficulty('HARD'))


if __name__ == '__main__':
    unittest.main()
