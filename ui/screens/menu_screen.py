from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

from core.game_state import GameScreen
from ui.dialogs import AchievementsDialog, HowToPlayDialog, LeaderboardDialog, VolumeDialog
from ui.screens import BaseScreen, make_button, make_label, make_panel, panel_layout
from ui.styles import GAP, GAP_SECTION, GAP_TIGHT, SIZE_DISPLAY
from ui.widgets.pixel import PixelIconButton, PixelTitle


class MenuScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addStretch(3)

        outer.addWidget(PixelTitle("GRAPHITI", SIZE_DISPLAY), alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(GAP)
        outer.addWidget(make_label("A GRAPH COLORING GAME", role="caption"))
        outer.addSpacing(GAP_SECTION * 2)

        panel = self.fit(make_panel(), 0.36, 500, 620)
        layout = panel_layout(panel)
        self.play_btn = make_button("PLAY", self.on_play_clicked, icon="play")
        layout.addWidget(self.play_btn)
        layout.addWidget(make_button("LEADERBOARD", self.show_leaderboard, icon="star"))
        layout.addWidget(make_button("QUIT", QApplication.quit, icon="close"))
        layout.addSpacing(GAP_TIGHT)
        self.banked_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.banked_label)
        outer.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(4)

        corners = QHBoxLayout()
        corners.setSpacing(GAP)
        self.guide_btn = PixelIconButton("guide", "GUIDE")
        self.guide_btn.clicked.connect(self.show_guide)
        self.achievements_btn = PixelIconButton("trophy", "ACHIEVEMENTS")
        self.achievements_btn.clicked.connect(self.show_achievements)
        self.volume_btn = PixelIconButton("sound", "VOLUME")
        self.volume_btn.clicked.connect(self.show_volume)
        corners.addWidget(self.guide_btn)
        corners.addWidget(self.achievements_btn)
        corners.addStretch(1)
        corners.addWidget(self.volume_btn)
        outer.addLayout(corners)

    def on_show(self):
        achievements = self.game_state.achievement_system
        self.banked_label.setText(f"BANKED: {self.game_state.total_banked:,} | "
                                  f"BADGES: {len(achievements.badges_earned)} | "
                                  f"SOLVED: {achievements.graphs_solved}")
        self.update_volume_icon()
        self.play_btn.setFocus()

    def update_volume_icon(self):
        settings = self.main_window.settings
        self.volume_btn.set_icon("muted" if settings.muted or settings.volume == 0 else "sound")

    def on_play_clicked(self):
        self.main_window.show_screen(GameScreen.MODE_SELECT)

    def show_guide(self):
        HowToPlayDialog(self).exec()

    def show_leaderboard(self):
        LeaderboardDialog(self.game_state.leaderboard_system, self,
                          planar=self.game_state.planar_leaderboard).exec()

    def show_achievements(self):
        AchievementsDialog(self.game_state.achievement_system, self).exec()

    def show_volume(self):
        VolumeDialog(self.main_window.settings, self.main_window.music, self,
                     on_change=self.update_volume_icon).exec()
