from tests import support

import random
import unittest

from algorithms.planar_puzzle import measure
from algorithms.solvers import optimal_coloring
from core.constants import (GRAPH_CONSTRAINTS, RACE_COLORING, RACE_DISQUALIFY_BELOW, RACE_PLANAR,
                            RACE_SECONDS)
from core.race import Race

PLAYERS = {0: "HOST", 1: "ANN", 2: "BOB"}


def solution(puzzle: dict):
    colors = optimal_coloring(puzzle["n"], [tuple(e) for e in puzzle["edges"]], puzzle["chi"],
                              timeout_ms=1000)
    return [colors[v] for v in range(puzzle["n"])]


class RaceCase(unittest.TestCase):
    def make(self, mode=RACE_COLORING, seed=3, players=None):
        self.now = [0.0]
        race = Race(mode, players or PLAYERS, rng=random.Random(seed), clock=lambda: self.now[0],
                    search_seconds=0.01)
        race.start()
        return race

    def solve(self, race, pid):
        index = race.racers[pid].index
        return race.submit(pid, index, solution(race.puzzle(index)))


class TestColoringRace(RaceCase):
    def test_durations(self):
        self.assertEqual(RACE_SECONDS[RACE_COLORING], 420)
        self.assertEqual(RACE_SECONDS[RACE_PLANAR], 600)

    def test_everyone_gets_the_same_sequence_from_the_full_ranges(self):
        race = self.make()
        puzzles = [race.puzzle(i) for i in range(30)]
        for before, after in zip(puzzles, puzzles[1:]):
            self.assertNotEqual(before["type"], after["type"])
        for puzzle in puzzles:
            lo, hi = GRAPH_CONSTRAINTS[puzzle["type"]]
            self.assertTrue(lo <= puzzle["n"] <= hi)
            self.assertEqual(len(puzzle["layout"]), puzzle["n"])
        self.assertIs(race.puzzle(4), puzzles[4])
        self.assertGreater(max(p["n"] for p in puzzles), 25)

    def test_only_a_proper_full_coloring_counts(self):
        race = self.make()
        puzzle = race.puzzle(0)
        good = solution(puzzle)
        self.assertFalse(race.submit(1, 0, good[:-1])[0])
        self.assertFalse(race.submit(1, 0, [None] * puzzle["n"])[0])
        self.assertFalse(race.submit(1, 0, [0] * puzzle["n"])[0])
        self.assertFalse(race.submit(1, 3, good)[0])
        self.assertEqual(race.racers[1].solved, 0)
        self.assertEqual(race.submit(1, 0, good), (True, None))
        self.assertEqual((race.racers[1].solved, race.racers[1].index), (1, 1))
        self.assertFalse(race.submit(1, 0, good)[0])

    def test_skips_cost_one_more_each_time(self):
        race = self.make()
        totals = []
        for _ in range(4):
            self.assertTrue(race.skip(2, race.racers[2].index)[0])
            totals.append(race.racers[2].score)
        self.assertEqual(totals, [-1, -3, -6, -10])
        self.assertFalse(race.racers[2].disqualified)
        self.assertEqual(race.skip_cost(2), 5)

    def test_score_below_minus_ten_disqualifies_at_once(self):
        race = self.make()
        for _ in range(5):
            race.skip(2, race.racers[2].index)
        racer = race.racers[2]
        self.assertEqual(racer.score, -15)
        self.assertLess(racer.score, RACE_DISQUALIFY_BELOW)
        self.assertTrue(racer.disqualified)
        self.assertFalse(race.skip(2, racer.index)[0])
        self.assertFalse(race.submit(2, racer.index, [])[0])

    def test_solving_keeps_a_skipper_in_the_match(self):
        race = self.make()
        self.assertTrue(self.solve(race, 1)[0])
        self.assertTrue(self.solve(race, 1)[0])
        for _ in range(4):
            race.skip(1, race.racers[1].index)
        self.assertEqual(race.racers[1].score, -8)
        race.finish()
        self.assertFalse(race.racers[1].disqualified)

    def test_ranking_is_score_then_who_got_there_first(self):
        race = self.make()
        self.now[0] = 10
        self.solve(race, 2)
        self.now[0] = 20
        self.solve(race, 1)
        self.now[0] = 30
        self.solve(race, 0)
        self.solve(race, 0)
        rows = race.standings()
        self.assertEqual([row["name"] for row in rows], ["HOST", "BOB", "ANN"])
        self.assertEqual([row["rank"] for row in rows], [1, 2, 3])
        self.assertEqual(race.winner()["name"], "HOST")

    def test_nobody_solving_means_no_winner(self):
        race = self.make()
        race.skip(1, 0)
        race.finish()
        self.assertIsNone(race.winner())
        self.assertTrue(all(row["dq"] and row["rank"] is None for row in race.standings()))

    def test_leaving_and_time_up_stop_a_player(self):
        race = self.make()
        race.leave(1)
        self.assertFalse(self.solve(race, 1)[0])
        self.assertTrue(next(r for r in race.standings() if r["id"] == 1)["left"])
        self.now[0] = RACE_SECONDS[RACE_COLORING] + 1
        self.assertTrue(race.time_up())
        self.assertFalse(self.solve(race, 0)[0])


class TestPlanarRace(RaceCase):
    def test_no_skips_and_only_crossing_free_drawings_count(self):
        race = self.make(RACE_PLANAR)
        data = race.puzzle(0)
        puzzle = race.planar[0]
        self.assertFalse(race.skip(1, 0)[0])
        self.assertFalse(race.submit(1, 0, data["start"])[0])
        self.assertFalse(race.submit(1, 0, [[0, 0]] * puzzle.n)[0])
        self.assertTrue(race.submit(1, 0, [list(p) for p in puzzle.solution])[0])
        key = measure(puzzle.n, puzzle.edges, puzzle.solution)
        self.assertEqual((race.racers[1].area, race.racers[1].box), key)

    def test_ranking_is_solved_then_area_then_box_then_time(self):
        race = self.make(RACE_PLANAR, players={0: "A", 1: "B", 2: "C", 3: "D"})
        race.puzzle(0)
        puzzle = race.planar[0]
        wide = [(x * 2, y) for x, y in puzzle.solution]
        self.now[0] = 5
        self.assertTrue(race.submit(0, 0, wide)[0])
        self.now[0] = 9
        self.assertTrue(race.submit(1, 0, puzzle.solution)[0])
        self.now[0] = 12
        self.assertTrue(race.submit(2, 0, puzzle.solution)[0])
        race.finish()
        rows = race.standings()
        self.assertEqual([row["name"] for row in rows], ["B", "C", "A", "D"])
        self.assertTrue(rows[3]["dq"])
        self.assertLess(rows[0]["area"], rows[2]["area"])

    def test_summary_names_the_smallest_player_layout(self):
        race = self.make(RACE_PLANAR)
        race.puzzle(0)
        puzzle = race.planar[0]
        race.submit(1, 0, [(x * 2, y) for x, y in puzzle.solution])
        race.submit(2, 0, puzzle.solution)
        race.improve(0.01)
        entry = race.planar_summary()[0]
        self.assertEqual(entry["best_name"], "BOB")
        self.assertEqual(tuple(entry["best_key"]), measure(puzzle.n, puzzle.edges, puzzle.solution))
        self.assertLessEqual(tuple(entry["program_key"]), tuple(entry["best_key"]))
        self.assertIsNone(race.planar_summary()[1]["best_name"])


if __name__ == "__main__":
    unittest.main()
