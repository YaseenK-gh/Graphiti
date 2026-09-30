"""EASY / MEDIUM / HARD selection."""

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from core.constants import (DIFFICULTY_CONFIG, DIFFICULTY_ORDER, GRAPH_DISPLAY_NAMES, HINT_COSTS,
                            UI_EASY, UI_INK, UI_MEDIUM)
from core.game_state import GameScreen
from core.graph_manager import GraphManager
from core.scoring import ScoringSystem
from ui.screens import BaseScreen, make_button, make_divider, make_label, make_panel
from ui.widgets.pixel import PixelCard
from ui.widgets.timer_widget import format_time

DIFFICULTY_COLORS = {'EASY': UI_EASY, 'MEDIUM': UI_MEDIUM, 'HARD': UI_INK}
SHORT_NAMES = {'COMPLETE_BIPARTITE': "COMPLETE BIP.", 'NEAR_TRIANGULATION': "NEAR TRIANG."}


class DifficultySelectScreen(BaseScreen):

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.cards: Dict[str, PixelCard] = {}
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = make_panel()
        panel.setFixedWidth(900)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        layout.addWidget(make_label("SELECT DIFFICULTY", role="subtitle"))

        row = QHBoxLayout()
        row.setSpacing(16)
        for difficulty in DIFFICULTY_ORDER:
            card = PixelCard(difficulty, self.card_lines(difficulty), DIFFICULTY_COLORS[difficulty])
            card.clicked.connect(lambda _=False, d=difficulty: self.start_difficulty(d))
            row.addWidget(card)
            self.cards[difficulty] = card
        layout.addLayout(row)

        layout.addWidget(make_label("CLOSING MID-RUN IS NOT SAVED: A DIFFICULTY ALWAYS RESTARTS "
                                    "FROM GRAPH 1", role="caption", wrap=True))
        layout.addWidget(make_divider())
        layout.addWidget(make_button("◄ BACK", self.on_back_clicked, small=True))
        outer.addWidget(panel)

    @staticmethod
    def card_lines(difficulty: str) -> List[str]:
        config = DIFFICULTY_CONFIG[difficulty]
        types = [SHORT_NAMES.get(t, GRAPH_DISPLAY_NAMES[t]) for t in config['graph_types']]
        return ([f"{config['num_graphs']} GRAPHS", ""] + types
                + ["", f"MAX BONUS <{format_time(ScoringSystem.max_time_threshold(difficulty))}",
                   f"HINT: {HINT_COSTS[difficulty]:,} PTS"])

    def on_show(self):
        self.cards[DIFFICULTY_ORDER[0]].setFocus()

    def start_difficulty(self, difficulty: str):
        queue = GraphManager.generate_queue_for_difficulty(difficulty)
        self.game_state.start_difficulty(difficulty, queue)
        self.main_window.show_screen(GameScreen.PRE_GAME)

    def on_back_clicked(self):
        self.main_window.show_screen(GameScreen.MODE_SELECT)
