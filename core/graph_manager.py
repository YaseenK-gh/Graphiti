import logging
import random
from typing import List, Optional, Tuple

from algorithms.generators import generate_graph_full
from algorithms.layouts import compute_layout
from algorithms.solvers import compute_chromatic_number
from core.constants import DIFFICULTY_CONFIG, GRAPH_CONSTRAINTS
from core.game_state import Graph

logger = logging.getLogger(__name__)


class GraphManager:
    @staticmethod
    def generate_queue_for_difficulty(difficulty: str, rng=None) -> List[str]:
        rng = rng or random
        queue = [t for t in DIFFICULTY_CONFIG[difficulty]['graph_types']
                 for _ in range(DIFFICULTY_CONFIG[difficulty]['graphs_per_type'])]
        rng.shuffle(queue)
        return queue

    @staticmethod
    def default_n(graph_type: str) -> int:
        min_n, max_n = GRAPH_CONSTRAINTS[graph_type]
        return min_n + (max_n - min_n) // 3

    @staticmethod
    def generate_graph(graph_type: str, n: int) -> Graph:
        min_n, max_n = GRAPH_CONSTRAINTS.get(graph_type, (1, 100))
        if not (min_n <= n <= max_n):
            raise ValueError(f"n={n} outside constraints for {graph_type}")

        vertices, edges, positions = generate_graph_full(graph_type, n)
        chromatic_number = compute_chromatic_number(graph_type, n, edges)
        layout = compute_layout(graph_type, n, vertices, edges, positions)
        return Graph(type=graph_type, n=n, vertices=vertices, edges=edges,
                     chromatic_number=chromatic_number, layout=layout)

    @staticmethod
    def suggested_lower_n(graph_type: str, n: int) -> int:
        return max(GRAPH_CONSTRAINTS[graph_type][0], n - 5)

    @staticmethod
    def generate_graph_safe(graph_type: str, n: int) -> Tuple[Optional[Graph], Optional[str]]:
        if graph_type not in GRAPH_CONSTRAINTS:
            return None, f"Unknown graph type: {graph_type}."
        min_n, max_n = GRAPH_CONSTRAINTS[graph_type]
        if not isinstance(n, int) or not (min_n <= n <= max_n):
            return None, f"Invalid n={n} for {graph_type}. Must be between {min_n} and {max_n}."
        try:
            return GraphManager.generate_graph(graph_type, n), None
        except TimeoutError:
            logger.exception("Graph generation timed out (%s, n=%d)", graph_type, n)
            return None, (f"Graph generation timed out. Try a smaller n "
                          f"(currently {n}, suggest {GraphManager.suggested_lower_n(graph_type, n)}).")
        except Exception as e:
            logger.exception("Graph generation failed (%s, n=%d)", graph_type, n)
            return None, f"Graph generation error: {e}. Try a smaller n."
