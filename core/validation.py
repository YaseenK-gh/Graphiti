"""Validation for every free-text input the player can type."""

import re
from typing import Optional, Tuple

from core.constants import GRAPH_CONSTRAINTS, GRAPH_DISPLAY_NAMES, PLAYER_NAME_MAX_LEN


def validate_n(text: Optional[str], graph_type: Optional[str],
               prev_n: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    """Validate an n (vertex count) input. Returns (n or None, error message or None).

    prev_n is the n of the previous STANDARD level of this type: n must exceed it,
    unless it was already the maximum, in which case n is locked at the maximum.
    """
    if graph_type not in GRAPH_CONSTRAINTS:
        return None, "Select a graph type first."
    if text is None or not text.strip():
        return None, "Please enter a number."
    text = text.strip()
    if not re.fullmatch(r"[+-]?\d+", text):
        return None, "Please enter a valid integer."
    if len(text) > 6:
        return None, "That number is far too large."
    n = int(text)
    if n <= 0:
        return None, "Number must be positive."
    min_n, max_n = GRAPH_CONSTRAINTS[graph_type]
    if not (min_n <= n <= max_n):
        return None, f"For {GRAPH_DISPLAY_NAMES[graph_type]}, n must be {min_n}–{max_n}."
    if prev_n is not None:
        if prev_n >= max_n and n != max_n:
            return None, f"Locked at the maximum n = {max_n} for this run."
        if prev_n < max_n and n <= prev_n:
            return None, (f"n must be greater than {prev_n} "
                          f"(your last {GRAPH_DISPLAY_NAMES[graph_type]} level).")
    return n, None


def validate_player_name(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validate a leaderboard name. Returns (normalized UPPERCASE name or None, error or None)."""
    name = " ".join((text or "").split())  # Trim and collapse inner whitespace.
    if not name:
        return None, "Please enter a name."
    if len(name) > PLAYER_NAME_MAX_LEN:
        return None, f"Name must be at most {PLAYER_NAME_MAX_LEN} characters."
    if not re.fullmatch(r"[A-Za-z0-9 _.\-]+", name):
        return None, "Use letters, numbers, spaces, - _ . only."
    return name.upper(), None
