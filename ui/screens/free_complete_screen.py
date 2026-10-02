from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from core.constants import GRAPH_DISPLAY_NAMES, UI_BAD_ON_LIGHT, UI_GOOD_ON_LIGHT
from core.achievements import badge_name
from core.game_state import GameScreen
from ui.styles import GAP
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel, panel_layout,
                        set_text_color)
from ui.widgets.timer_widget import format_time


class FreeCompleteScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(), 0.52, 700, 820)
        layout = panel_layout(panel)

        self.title_label = make_label(role="title")
        layout.addWidget(self.title_label)
        self.info_label = make_label(role="caption")
        layout.addWidget(self.info_label)
        layout.addWidget(make_divider())
        self.time_label = make_label(role="heading")
        layout.addWidget(self.time_label)
        self.colors_label = make_label()
        layout.addWidget(self.colors_label)
        self.verdict_label = make_label(role="body", wrap=True)
        layout.addWidget(self.verdict_label)
        self.badges_label = make_label(role="caption", wrap=True)
        set_text_color(self.badges_label, UI_GOOD_ON_LIGHT)
        layout.addWidget(self.badges_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.again_btn = make_button("PLAY AGAIN", self.on_play_again_clicked, small=True)
        buttons.addWidget(self.again_btn)
        buttons.addWidget(make_button("NEW GRAPH", self.on_new_graph_clicked, small=True))
        buttons.addWidget(make_button("MENU", self.on_menu_clicked, small=True))
        layout.addLayout(buttons)
        outer.addWidget(panel)

    def on_show(self):
        result = self.game_state.last_level_result
        if result.forfeited:
            self.title_label.setText("SOLUTION REVEALED")
            set_text_color(self.title_label, UI_BAD_ON_LIGHT)
        else:
            self.title_label.setText("GRAPH SOLVED!")
            set_text_color(self.title_label, None)
        self.info_label.setText(f"{GRAPH_DISPLAY_NAMES[result.graph_type]} | n = {result.n}")
        self.time_label.setText(f"TIME {format_time(result.time_seconds)}")
        self.colors_label.setText(f"COLORS USED: {result.colors_used} | BEST: {result.chromatic_number}")
        good = None
        if result.forfeited:
            verdict = "Study the coloring, then try again."
        elif result.colors_used <= result.chromatic_number:
            verdict, good = "OPTIMAL COLORING - you hit the chromatic number!", UI_GOOD_ON_LIGHT
        elif result.colors_used == result.chromatic_number + 1:
            verdict = "One color above optimal. So close!"
        else:
            verdict = (f"Valid, but it can be done with {result.chromatic_number} colors. "
                       f"Can you do it with fewer colors?")
        self.verdict_label.setText(verdict)
        set_text_color(self.verdict_label, good)
        self.show_new_badges()
        self.again_btn.setFocus()

    def show_new_badges(self):
        badges = self.game_state.take_pending_badges()
        self.badges_label.setText("BADGE UNLOCKED: " + ", ".join(badge_name(b) for b in badges)
                                  if badges else "")
        self.badges_label.setVisible(bool(badges))

    def on_play_again_clicked(self):
        state = self.game_state
        select = self.main_window.screens[GameScreen.FREE_GRAPH_SELECT]
        if not select.start_free_graph(state.selected_graph_type, state.selected_n):
            self.main_window.show_screen(GameScreen.FREE_GRAPH_SELECT)

    def on_new_graph_clicked(self):
        self.main_window.show_screen(GameScreen.FREE_GRAPH_SELECT)

    def on_menu_clicked(self):
        self.main_window.show_screen(GameScreen.MENU)
