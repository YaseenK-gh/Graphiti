"""Main menu (entry point)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout

from core.game_state import GameScreen
from ui.dialogs import AchievementsDialog, HowToPlayDialog, LeaderboardDialog
from ui.screens import BaseScreen, make_button, make_label, make_panel


class MenuScreen(BaseScreen):

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = make_panel()
        panel.setFixedWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(36, 32, 36, 26)
        layout.setSpacing(12)

        layout.addWidget(make_label("GRAPH COLORING", role="title"))
        layout.addWidget(make_label("— COLOR THEOREM —", role="caption"))
        layout.addSpacing(12)

        self.play_btn = make_button("▶ PLAY GAME", self.on_play_clicked)
        layout.addWidget(self.play_btn)
        for text, slot in (("? HOW TO PLAY", self.show_how_to_play),
                           ("★ LEADERBOARD", self.show_leaderboard),
                           ("✦ ACHIEVEMENTS", self.show_achievements),
                           ("✕ QUIT", QApplication.quit)):
            layout.addWidget(make_button(text, slot))

        layout.addSpacing(8)
        self.banked_label = make_label(role="caption")
        layout.addWidget(self.banked_label)
        outer.addWidget(panel)

    def on_show(self):
        achievements = self.game_state.achievement_system
        self.banked_label.setText(f"BANKED: {self.game_state.total_banked:,}  ·  "
                                  f"BADGES: {len(achievements.badges_earned)}  ·  "
                                  f"SOLVED: {achievements.graphs_solved}")
        self.play_btn.setFocus()

    def on_play_clicked(self):
        self.main_window.show_screen(GameScreen.MODE_SELECT)

    def show_how_to_play(self):
        HowToPlayDialog(self).exec()

    def show_leaderboard(self):
        LeaderboardDialog(self.game_state.leaderboard_system, self).exec()

    def show_achievements(self):
        AchievementsDialog(self.game_state.achievement_system, self).exec()
