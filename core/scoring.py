from typing import Dict, List, Tuple

from core.constants import (ALL_MAX_TIME_MULTIPLIER, DIFFICULTY_CONFIG, NEAR_OPTIMAL_COLORING_BONUS,
                            OPTIMAL_COLORING_BONUS)


class ScoringSystem:
    @staticmethod
    def time_tiers(difficulty: str) -> List[Tuple[int, int]]:
        tiers = [(int(key.split('_')[1]), bonus)
                 for key, bonus in DIFFICULTY_CONFIG[difficulty]['time_bonus'].items()
                 if key.startswith('under')]
        return sorted(tiers)

    @staticmethod
    def max_time_threshold(difficulty: str) -> int:
        return ScoringSystem.time_tiers(difficulty)[0][0]

    @staticmethod
    def _get_time_bonus(difficulty: str, time_seconds: float) -> int:
        tiers = ScoringSystem.time_tiers(difficulty)
        for threshold, bonus in tiers:
            if time_seconds < threshold:
                return bonus
        return DIFFICULTY_CONFIG[difficulty]['time_bonus'].get(f'over_{tiers[-1][0]}', 0)

    @staticmethod
    def _get_optimality_bonus(colors_used: int, chromatic_number: int) -> int:
        if colors_used <= chromatic_number:
            return OPTIMAL_COLORING_BONUS
        if colors_used == chromatic_number + 1:
            return NEAR_OPTIMAL_COLORING_BONUS
        return 0

    @staticmethod
    def score_breakdown(difficulty: str, time_seconds: float, n: int,
                        colors_used: int, chromatic_number: int) -> Dict[str, int]:
        config = DIFFICULTY_CONFIG[difficulty]
        breakdown = {
            'base': config['base_points'],
            'time_bonus': ScoringSystem._get_time_bonus(difficulty, time_seconds),
            'vertex_bonus': n * config['vertex_multiplier'],
            'optimality_bonus': ScoringSystem._get_optimality_bonus(colors_used, chromatic_number),
        }
        breakdown['total'] = max(0, sum(breakdown.values()))
        return breakdown

    @staticmethod
    def compute_level_score(difficulty: str, time_seconds: float, n: int,
                            colors_used: int, chromatic_number: int) -> int:
        return ScoringSystem.score_breakdown(difficulty, time_seconds, n,
                                             colors_used, chromatic_number)['total']

    @staticmethod
    def apply_reset_penalty(provisional_score: int, difficulty: str) -> int:
        penalty_rate = DIFFICULTY_CONFIG[difficulty]['reset_penalty']
        return max(0, int(provisional_score * (1 - penalty_rate)))

    @staticmethod
    def check_max_time_bonus(time_seconds: float, difficulty: str) -> bool:
        return time_seconds < ScoringSystem.max_time_threshold(difficulty)

    @staticmethod
    def apply_500_percent_bonus(provisional_score: int, all_max_bonus: bool) -> int:
        if all_max_bonus:
            return int(provisional_score * ALL_MAX_TIME_MULTIPLIER)
        return provisional_score
