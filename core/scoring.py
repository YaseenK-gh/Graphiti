"""Level and difficulty scoring."""

from typing import Dict, List, Tuple

from core.constants import (ALL_MAX_TIME_MULTIPLIER, DIFFICULTY_CONFIG, NEAR_OPTIMAL_COLORING_BONUS,
                            OPTIMAL_COLORING_BONUS)


class ScoringSystem:
    """Compute level and difficulty scores."""

    @staticmethod
    def time_tiers(difficulty: str) -> List[Tuple[int, int]]:
        """[(seconds, bonus), ...] sorted by threshold. Numeric sort matters:
        a string sort would put 'under_120' before 'under_60'."""
        tiers = [(int(key.split('_')[1]), bonus)
                 for key, bonus in DIFFICULTY_CONFIG[difficulty]['time_bonus'].items()
                 if key.startswith('under')]
        return sorted(tiers)

    @staticmethod
    def max_time_threshold(difficulty: str) -> int:
        """Seconds within which a level earns the maximum time bonus."""
        return ScoringSystem.time_tiers(difficulty)[0][0]

    @staticmethod
    def _get_time_bonus(difficulty: str, time_seconds: float) -> int:
        """Get time bonus based on difficulty and time."""
        tiers = ScoringSystem.time_tiers(difficulty)
        for threshold, bonus in tiers:
            if time_seconds < threshold:
                return bonus
        return DIFFICULTY_CONFIG[difficulty]['time_bonus'].get(f'over_{tiers[-1][0]}', 0)

    @staticmethod
    def _get_optimality_bonus(colors_used: int, chromatic_number: int) -> int:
        """Bonus for optimal (χ colors) or near-optimal (χ+1) colorings.

        `<=` rather than `==`: if the χ solver timed out it reports the safe upper
        bound, so a player who beats it still counts as optimal.
        """
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
        """Compute score for a single level."""
        return ScoringSystem.score_breakdown(difficulty, time_seconds, n,
                                             colors_used, chromatic_number)['total']

    @staticmethod
    def apply_reset_penalty(provisional_score: int, difficulty: str) -> int:
        """Apply reset penalty (30% loss)."""
        penalty_rate = DIFFICULTY_CONFIG[difficulty]['reset_penalty']
        return max(0, int(provisional_score * (1 - penalty_rate)))

    @staticmethod
    def check_max_time_bonus(time_seconds: float, difficulty: str) -> bool:
        """Check if this level hit the max time bonus."""
        return time_seconds < ScoringSystem.max_time_threshold(difficulty)

    @staticmethod
    def apply_500_percent_bonus(provisional_score: int, all_max_bonus: bool) -> int:
        """Apply 500% bonus if all graphs hit max time bonus."""
        if all_max_bonus:
            return int(provisional_score * ALL_MAX_TIME_MULTIPLIER)
        return provisional_score
