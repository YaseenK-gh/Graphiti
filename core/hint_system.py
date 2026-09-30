"""Hint rules and hint generation.

A hint names one vertex and a color for it. Rather than just "a color no
neighbour currently uses" (which can lead the player into a dead end), the hint
comes from a full proper completion of the player's current conflict-free
coloring, so following hints never makes the puzzle unsolvable.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from algorithms.coloring import conflicting_vertices
from algorithms.solvers import SolverTimeout, build_adjacency_list, extend_coloring, make_deadline
from core.constants import (HINT_COOLDOWN_MS, HINT_COSTS, HINT_SOLVER_TIMEOUT_MS,
                            MAX_HINTS_PER_LEVEL, PALETTE)

if TYPE_CHECKING:
    from core.game_state import Graph


class HintSystem:

    # Difficulty-scaled hint costs (makes players think strategically)
    HINT_COSTS = HINT_COSTS
    MAX_HINTS_PER_LEVEL = MAX_HINTS_PER_LEVEL
    COOLDOWN_MS = HINT_COOLDOWN_MS

    @staticmethod
    def get_hint_cost(difficulty: Optional[str]) -> int:
        """Get hint cost for a difficulty level."""
        return HintSystem.HINT_COSTS.get(difficulty, 350)

    @staticmethod
    def can_buy_hint(available_points: int, difficulty: str) -> bool:
        """Check if player has enough points for one hint."""
        return available_points >= HintSystem.get_hint_cost(difficulty)

    @staticmethod
    def apply_hint_cost(provisional_score: int, difficulty: str) -> Tuple[int, bool]:
        """Deduct hint cost from provisional score. Returns (new_provisional_score, success)."""
        cost = HintSystem.get_hint_cost(difficulty)
        if provisional_score >= cost:
            return provisional_score - cost, True
        return provisional_score, False

    @staticmethod
    def get_hint_for_vertex(graph: "Graph", coloring: Dict[int, Optional[int]],
                            timeout_ms: float = HINT_SOLVER_TIMEOUT_MS) -> Optional[Tuple[int, int]]:
        """Return (vertex_id, suggested_color), or None if the graph is already solved.

        Targets the most constrained uncolored vertex (most colored neighbours);
        if everything is colored but conflicts remain, targets a conflicting vertex.
        """
        n = graph.n
        palette_size = len(PALETTE)
        adj = build_adjacency_list(n, graph.edges)
        bad = conflicting_vertices(coloring, graph.edges)
        fixed = {v: c for v, c in coloring.items() if c is not None and v not in bad}

        uncolored: List[int] = [v for v in graph.vertices if coloring.get(v) is None]
        if not uncolored and not bad:
            return None

        def most_constrained(candidates: List[int]) -> int:
            return max(candidates, key=lambda v: (sum(1 for u in adj[v] if u in fixed), len(adj[v]), -v))

        completion = None
        deadline = make_deadline(timeout_ms)
        try:
            start_k = max(graph.chromatic_number, len(set(fixed.values())), 1)
            for k in range(start_k, palette_size + 1):
                completion = extend_coloring(adj, n, k, precolored=fixed,
                                             palette_size=palette_size, deadline=deadline)
                if completion is not None:
                    break
        except SolverTimeout:
            completion = None
        if completion is not None:
            if uncolored:
                target = most_constrained(uncolored)
            else:
                # Fixing a conflict: pick a vertex whose suggested color actually changes.
                changed = [v for v in sorted(bad) if completion[v] != coloring.get(v)]
                target = most_constrained(changed or sorted(bad))
            return target, completion[target]

        target = most_constrained(uncolored or sorted(bad))
        # Fallback: the color used by the fewest of the target's (fixed) neighbours,
        # preferring colors already in play, then the lowest index.
        in_play = set(fixed.values())
        neighbour_counts = [sum(1 for u in adj[target] if fixed.get(u) == c) for c in range(palette_size)]
        color = min(range(palette_size), key=lambda c: (neighbour_counts[c], c not in in_play, c))
        return target, color
