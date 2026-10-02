from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout

from core.achievements import BADGE_INFO, badge_name
from core.constants import DIFFICULTY_CONFIG, PLAYER_NAME_MAX_LEN, UI_GOLD, UI_INNER, UI_LIME
from core.game_state import GameScreen
from ui.dialogs import LeaderboardDialog
from ui.styles import GAP
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel, panel_layout,
                        set_text_color)


class PostDifficultyScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(dark=True), 0.6, 720, 900)
        layout = panel_layout(panel)

        self.complete_label = make_label(role="caption")
        layout.addWidget(self.complete_label)
        self.title_label = make_label(role="title")
        layout.addWidget(self.title_label)
        self.message_label = make_label(role="body", wrap=True)
        layout.addWidget(self.message_label)
        layout.addWidget(make_divider(dark=True))
        self.provisional_label = make_label()
        layout.addWidget(self.provisional_label)
        self.multiplier_label = make_label(role="caption")
        layout.addWidget(self.multiplier_label)
        self.banked_label = make_label(role="heading")
        layout.addWidget(self.banked_label)
        self.stats_label = make_label(role="caption")
        layout.addWidget(self.stats_label)

        self.badges_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.badges_label)
        self.streak_label = make_label(role="caption")
        layout.addWidget(self.streak_label)
        layout.addWidget(make_divider(dark=True))

        entry_row = QHBoxLayout()
        entry_row.setSpacing(GAP)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("YOUR NAME")
        self.name_input.setMaxLength(PLAYER_NAME_MAX_LEN + 4)
        self.name_input.returnPressed.connect(self.on_submit_clicked)
        self.name_input.textChanged.connect(lambda _t: self.name_error_label.setText(""))
        entry_row.addWidget(self.name_input, 3)
        self.submit_btn = make_button("SUBMIT SCORE", self.on_submit_clicked, small=True)
        entry_row.addWidget(self.submit_btn, 2)
        layout.addLayout(entry_row)
        self.name_error_label = make_label(role="error")
        layout.addWidget(self.name_error_label)
        layout.addWidget(make_button("VIEW LEADERBOARD", self.show_leaderboard, variant="dark", icon="star",
                                     small=True))

        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.menu_btn = make_button("MAIN MENU", self.on_menu_clicked, icon="back")
        self.next_btn = make_button("NEXT DIFFICULTY", self.on_next_difficulty_clicked, icon="play")
        buttons.addWidget(self.menu_btn)
        buttons.addWidget(self.next_btn)
        layout.addLayout(buttons)
        outer.addWidget(panel)

    def on_show(self):
        state = self.game_state
        result = state.last_difficulty_result
        config = DIFFICULTY_CONFIG[result.difficulty]
        self.complete_label.setText(f"{result.difficulty} COMPLETE")
        self.title_label.setText(config['title'])
        self.message_label.setText(config['message'])
        self.provisional_label.setText(f"PROVISIONAL SCORE: {result.provisional_score:,}")
        if result.all_max_time:
            self.multiplier_label.setText("EVERY GRAPH HIT THE MAX TIME BONUS: X5")
            set_text_color(self.multiplier_label, UI_GOLD)
        else:
            self.multiplier_label.setText(f"MAX TIME BONUS ON {state.max_time_bonus_hits}/"
                                          f"{result.graph_count} GRAPHS (ALL NEEDED FOR X5)")
            set_text_color(self.multiplier_label, None)
        self.banked_label.setText(f"BANKED: {result.banked_score:,}")
        self.stats_label.setText(f"RESETS: {result.resets} | HINTS: {result.hints_used} | "
                                 f"FORFEITS: {result.forfeits} | "
                                 f"SESSION: {state.total_banked:,}")
        self.show_achievements()

        nxt = state.next_difficulty(result.difficulty)
        self.next_btn.setVisible(nxt is not None)
        if nxt:
            self.next_btn.setText(f"PLAY {nxt}")

        self.name_input.setEnabled(not result.submitted)
        self.submit_btn.setEnabled(not result.submitted)
        self.name_error_label.setText("")
        self.name_input.setFocus()

    def show_achievements(self):
        result = self.game_state.last_difficulty_result
        achievements = self.game_state.achievement_system
        total = f"{len(achievements.badges_earned)}/{len(BADGE_INFO)} BADGES"
        if result.new_badges:
            self.badges_label.setText("BADGES EARNED: " + ", ".join(badge_name(b) for b in result.new_badges)
                                      + f"  ({total})")
            set_text_color(self.badges_label, UI_LIME)
        else:
            self.badges_label.setText(f"NO NEW BADGES  ({total})")
            set_text_color(self.badges_label, UI_INNER)
        self.streak_label.setText(f"{result.difficulty} STREAK: {result.streak}"
                                  + ("  ON FIRE!" if result.streak >= 3 else "")
                                  + ("" if result.streak else "  (RESETS/FORFEITS BREAK STREAKS)"))

    def on_submit_clicked(self):
        rank, error = self.game_state.submit_score(self.name_input.text())
        if error:
            set_text_color(self.name_error_label, None)
            self.name_error_label.setText(error)
            return
        self.name_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        set_text_color(self.name_error_label, UI_LIME)
        self.name_error_label.setText(f"SAVED - RANK #{rank}" if rank else "SAVED (OUTSIDE THE TOP 100)")

    def show_leaderboard(self):
        LeaderboardDialog(self.game_state.leaderboard_system, self,
                          difficulty=self.game_state.last_difficulty_result.difficulty,
                          planar=self.game_state.planar_leaderboard).exec()

    def on_menu_clicked(self):
        self.main_window.show_screen(GameScreen.MENU)

    def on_next_difficulty_clicked(self):
        nxt = self.game_state.next_difficulty(self.game_state.last_difficulty_result.difficulty)
        if nxt:
            self.main_window.screens[GameScreen.DIFFICULTY_SELECT].start_difficulty(nxt)
