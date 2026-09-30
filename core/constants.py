"""Game-wide constants: theme, palette, graph constraints, difficulty and tuning values."""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Leaderboard / achievement JSON files live here. Tests point it at a temp dir.
DATA_DIR = os.environ.get("GRAPH_COLORING_DATA_DIR") or os.path.join(PROJECT_ROOT, "data")

# ─── Theme (pixel Game Boy, from the reference design) ────────────────────────
UI_BG = "#C8D4A0"            # Page background
UI_DOT = "#8A9A60"           # Page dot grid
UI_PANEL = "#B0C080"         # Light panels and the play area
UI_CARD = "#C0CC88"
UI_BUTTON = "#D0DC90"
UI_FIELD = "#E8F0C0"         # Text inputs and header strips
UI_INK = "#1A2A0A"           # Darkest text; dark panel fill
UI_BORDER = "#2A3A1A"        # Borders and hard shadows
UI_INNER = "#6A8040"         # Inner panel border, title shadow, captions on dark panels
UI_DARK_LINE = "#3A5A20"     # Dividers and secondary buttons on dark panels
UI_LIME = "#A8D060"          # Primary text on dark panels
UI_LIME_DIM = "#88A840"
UI_EASY = "#6A9A30"
UI_MEDIUM = "#B87820"
UI_GOLD = "#F0D060"
UI_DANGER_BG = "#5A1A1A"
UI_DANGER_TEXT = "#E08080"
UI_RED = "#E03030"
UI_TIMER_SHADOW = "#4A7010"
# Status text on light panels (dark panels use LIME / GOLD / DANGER_TEXT).
UI_MUTED_ON_LIGHT = "#4A6030"
UI_GOOD_ON_LIGHT = "#2F5A00"
UI_CAUTION_ON_LIGHT = "#8A5A10"
UI_BAD_ON_LIGHT = "#A02020"

# ─── Graph colors (10-color palette, keys 1–9 then 0) ─────────────────────────
PALETTE = [
    "#FF4D4D",  # 1 - Red
    "#FF9900",  # 2 - Orange
    "#FFE033",  # 3 - Yellow
    "#4DFF6E",  # 4 - Green
    "#33C9FF",  # 5 - Cyan
    "#6655FF",  # 6 - Purple
    "#FF55CC",  # 7 - Magenta
    "#9C6B3F",  # 8 - Brown (was White, which is indistinguishable from an uncolored node)
    "#A0A0A0",  # 9 - Gray
    "#00FFAA",  # 10 - Mint
]
PALETTE_NAMES = ["RED", "ORANGE", "YELLOW", "GREEN", "CYAN",
                 "PURPLE", "MAGENTA", "BROWN", "GRAY", "MINT"]
PALETTE_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]

# ─── Graph types ──────────────────────────────────────────────────────────────
GRAPH_TYPES = [
    'PATH', 'TREE', 'BIPARTITE', 'CYCLE',
    'COMPLETE_BIPARTITE', 'WHEEL', 'OUTERPLANAR', 'CHORDAL',
    'TRIANGLE_FREE', 'NEAR_TRIANGULATION', 'PLANAR',
]

# (min_n, max_n) — performance-tuned limits from the final plan.
GRAPH_CONSTRAINTS = {
    'PATH': (2, 60),
    'TREE': (3, 50),
    'BIPARTITE': (4, 45),
    'CYCLE': (3, 55),
    'COMPLETE_BIPARTITE': (4, 25),
    'WHEEL': (4, 35),
    'OUTERPLANAR': (4, 40),
    'CHORDAL': (4, 40),
    'TRIANGLE_FREE': (5, 40),
    'NEAR_TRIANGULATION': (5, 35),
    'PLANAR': (5, 45),
}

GRAPH_DISPLAY_NAMES = {t: t.replace('_', ' ') for t in GRAPH_TYPES}

GRAPH_DESCRIPTIONS = {
    'PATH': "A simple chain of connected vertices. One of the simplest graphs. "
            "Requires only 2 colors. Great for beginners.",
    'TREE': "A branching structure with no cycles. Common in nature and data structures. "
            "Requires only 2 colors because trees are bipartite.",
    'BIPARTITE': "Two separate groups with all edges between groups. No edges within groups. "
                 "Requires only 2 colors by definition.",
    'CYCLE': "Vertices arranged in a circular chain. Even cycles need 2 colors, "
             "odd cycles need 3 colors.",
    'COMPLETE_BIPARTITE': "All vertices in one group connect to all in another. "
                          "Requires only 2 colors. More edges than bipartite.",
    'WHEEL': "A hub vertex connected to all rim vertices in a cycle. "
             "Requires 3–4 colors depending on rim structure.",
    'OUTERPLANAR': "A graph that can be drawn with all vertices on the outer boundary. "
                   "Requires at most 3 colors.",
    'CHORDAL': "A graph with special structure (perfect elimination ordering). "
               "Requires colors equal to largest clique size.",
    'TRIANGLE_FREE': "A planar graph with no triangles. Requires at most 3 colors "
                     "(Grötzsch's theorem).",
    'NEAR_TRIANGULATION': "A planar graph where all interior faces are triangles. "
                          "Requires at most 4 colors (Four Color Theorem).",
    'PLANAR': "A graph drawable on paper with no edge crossings. "
              "Requires at most 4 colors (Four Color Theorem).",
}

# ─── Difficulty settings ──────────────────────────────────────────────────────
DIFFICULTY_ORDER = ['EASY', 'MEDIUM', 'HARD']
GRAPHS_PER_TYPE = 3

DIFFICULTY_CONFIG = {
    'EASY': {
        'base_points': 500,
        'graph_types': ['PATH', 'TREE', 'BIPARTITE', 'CYCLE'],
        'num_graphs': 12,  # 4 types × 3 each
        'time_bonus': {
            'under_30': 1000,
            'under_60': 500,
            'under_90': 200,
            'over_90': 0,
        },
        'vertex_multiplier': 5,
        'reset_penalty': 0.30,
        'title': 'THE NODE NOVICE',
        'message': "You've entered the graph realm. The fundamentals are yours. "
                   "Ready to build something bigger?",
    },
    'MEDIUM': {
        'base_points': 1500,
        'graph_types': ['COMPLETE_BIPARTITE', 'WHEEL', 'OUTERPLANAR', 'CHORDAL'],
        'num_graphs': 12,  # 4 types × 3 each (COMPLETE removed)
        'time_bonus': {
            'under_60': 1500,
            'under_120': 800,
            'under_180': 300,
            'over_180': 0,
        },
        'vertex_multiplier': 12,
        'reset_penalty': 0.30,
        'title': 'THE GRAPH ARCHITECT',
        'message': "Your designs are elegant. You've graduated from novice to architect. "
                   "The complex structures await.",
    },
    'HARD': {
        'base_points': 3000,
        'graph_types': ['TRIANGLE_FREE', 'NEAR_TRIANGULATION', 'PLANAR'],
        'num_graphs': 9,  # 3 types × 3 each
        'time_bonus': {
            'under_120': 2500,
            'under_210': 1500,
            'under_300': 500,
            'over_300': 0,
        },
        'vertex_multiplier': 20,
        'reset_penalty': 0.30,
        'title': 'THE CRYPTOGRAPHER',
        'message': "You've cracked the code. Few possess the mastery to decrypt these graphs. "
                   "You are legendary.",
    },
}

# ─── Scoring ──────────────────────────────────────────────────────────────────
OPTIMAL_COLORING_BONUS = 500
NEAR_OPTIMAL_COLORING_BONUS = 200
ALL_MAX_TIME_MULTIPLIER = 5.0  # "500% bonus" when every graph hits the max time bonus

# ─── Performance & error handling ─────────────────────────────────────────────
LAYOUT_TIMEOUT_MS = 1500
CHROMATIC_TIMEOUT_MS = 500
CHROMATIC_FALLBACK = 4  # Four Color Theorem upper bound for the planar families
HINT_SOLVER_TIMEOUT_MS = 300
SOLUTION_SOLVER_TIMEOUT_MS = 1000
GENERATION_MAX_RETRIES = 3
MEMORY_LIMIT_MB = 200
MIN_FPS = 30

# Logical scene size used by every layout (the view scales it to fit).
CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 800
CANVAS_PADDING = 40

# ─── Hint system (difficulty-scaled costs) ────────────────────────────────────
HINT_COSTS = {
    'EASY': 350,     # ~18-23% of typical level score
    'MEDIUM': 700,   # ~15-20% of typical level score
    'HARD': 1400,    # ~20-25% of typical level score
}
MAX_HINTS_PER_LEVEL = 5
HINT_COOLDOWN_MS = 10000

# ─── Node / edge rendering ────────────────────────────────────────────────────
DEFAULT_NODE_FILL = "#FFFFFF"     # White (uncolored)
DEFAULT_NODE_STROKE = UI_INK
DEFAULT_EDGE_STROKE = UI_BORDER
CONFLICT_EDGE_STROKE = UI_RED
NODE_STROKE_WIDTH = 3
EDGE_STROKE_WIDTH = 3
EDGE_CONFLICT_STROKE_WIDTH = 4
HOVER_GLOW_COLOR = UI_LIME
HOVER_GLOW_BLUR = 14
HINT_HALO_COLOR = UI_INK
NODE_RADIUS_MIN = 8
NODE_RADIUS_MAX = 14
NODE_RADIUS_SCALE = 300  # radius = clamp(300 / n, 8, 14)
SOLUTION_ANIMATION_MS = 1500

# ─── Achievements & leaderboard ───────────────────────────────────────────────
COLORBLIND_SOLVES = 50
LEADERBOARD_MAX_ENTRIES = 100  # per difficulty
LEADERBOARD_TOP_N = 10
PLAYER_NAME_MAX_LEN = 16
