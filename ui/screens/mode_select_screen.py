from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from core.game_state import GameMode, GameScreen
from ui.styles import GAP
from ui.screens import BaseScreen, make_button, make_divider, make_label, make_panel, panel_layout
from ui.widgets.pixel import PixelCard


class ModeSelectScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(), 0.82, 980, 1140)
        layout = panel_layout(panel)
        layout.addWidget(make_label("SELECT GAME MODE", role="subtitle"))

        cards = QHBoxLayout()
        cards.setSpacing(GAP)
        self.standard_card = PixelCard("STANDARD", ["3 DIFFICULTY LEVELS", "SCORING | TITLES",
                                                    "LEADERBOARD"])
        self.standard_card.clicked.connect(self.on_standard_clicked)
        self.free_card = PixelCard("FREE MODE", ["PRACTICE TRAINING", "ANY GRAPH | ANY SIZE",
                                                 "NO SCORING"])
        self.free_card.clicked.connect(self.on_free_clicked)
        self.planar_card = PixelCard("PLANAR DRAWING", ["UNTANGLE THE GRAPH", "10 MINUTE RUN",
                                                        "SMALLEST AREA WINS"])
        self.planar_card.clicked.connect(self.on_planar_clicked)
        cards.addWidget(self.standard_card)
        cards.addWidget(self.free_card)
        cards.addWidget(self.planar_card)
        layout.addLayout(cards)

        layout.addWidget(make_divider())
        layout.addWidget(make_button("BACK TO MENU", self.on_back_clicked, small=True, icon="back"))
        outer.addWidget(panel)

    def on_show(self):
        self.standard_card.setFocus()

    def on_standard_clicked(self):
        self.game_state.game_mode = GameMode.STANDARD
        self.main_window.show_screen(GameScreen.DIFFICULTY_SELECT)

    def on_free_clicked(self):
        self.game_state.start_free_mode()
        self.main_window.show_screen(GameScreen.FREE_GRAPH_SELECT)

    def on_planar_clicked(self):
        self.main_window.show_screen(GameScreen.PLANAR_INTRO)

    def on_back_clicked(self):
        self.main_window.show_screen(GameScreen.MENU)
