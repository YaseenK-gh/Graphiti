"""STANDARD mode: level completion with a score breakdown."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QMessageBox, QVBoxLayout

from core.constants import (DIFFICULTY_CONFIG, GRAPH_DISPLAY_NAMES, UI_BAD_ON_LIGHT,
                            UI_GOOD_ON_LIGHT, UI_MUTED_ON_LIGHT)
from core.achievements import badge_name
from core.game_state import GameScreen
from core.scoring import ScoringSystem
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        set_text_color)
from ui.widgets.timer_widget import format_time

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class PostLevelScreen(BaseScreen):

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = make_panel()
        panel.setFixedWidth(640)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 30, 40, 28)
        layout.setSpacing(12)

        self.title_label = make_label(role="title")
        layout.addWidget(self.title_label)
        self.info_label = make_label(role="caption")
        layout.addWidget(self.info_label)
        layout.addWidget(make_divider())

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        self.rows = {}
        for i, (key, text) in enumerate((("base", "BASE"), ("time_bonus", "TIME BONUS"),
                                         ("vertex_bonus", "VERTEX BONUS"),
                                         ("optimality_bonus", "OPTIMALITY"),
                                         ("score", "LEVEL SCORE"))):
            role = "heading" if key == "score" else None
            name = make_label(text, role=role, align=LEFT)
            value = make_label(role=role, align=RIGHT)
            detail = make_label(role="muted", align=LEFT)
            grid.addWidget(name, i, 0)
            grid.addWidget(detail, i, 1)
            grid.addWidget(value, i, 2)
            self.rows[key] = (value, detail)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addWidget(make_divider())

        self.max_time_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.max_time_label)
        self.provisional_label = make_label(role="badge")
        layout.addWidget(self.provisional_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.badges_label = make_label(role="body", wrap=True)
        set_text_color(self.badges_label, UI_GOOD_ON_LIGHT)
        layout.addWidget(self.badges_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.menu_btn = make_button("◄ MAIN MENU", self.on_menu_clicked)
        self.next_btn = make_button("NEXT GRAPH ▶ (ENTER)", self.on_next_clicked)
        buttons.addWidget(self.menu_btn)
        buttons.addWidget(self.next_btn, 2)
        layout.addLayout(buttons)
        outer.addWidget(panel)

        for key in ("Return", "Enter"):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self.on_next_clicked)

    def on_show(self):
        state = self.game_state
        result = state.last_level_result
        config = DIFFICULTY_CONFIG[state.difficulty]

        if result.forfeited:
            self.title_label.setText("LEVEL FORFEITED")
            set_text_color(self.title_label, UI_BAD_ON_LIGHT)
        else:
            self.title_label.setText("LEVEL COMPLETE")
            set_text_color(self.title_label, None)
        self.info_label.setText(f"{GRAPH_DISPLAY_NAMES[result.graph_type]} · n = {result.n} · "
                                f"TIME {format_time(result.time_seconds)}")

        details = {
            "base": state.difficulty,
            "time_bonus": format_time(result.time_seconds),
            "vertex_bonus": f"{result.n} × {config['vertex_multiplier']}",
            "optimality_bonus": f"{result.colors_used} COLORS / χ = {result.chromatic_number}",
            "score": "",
        }
        for key, (value, detail) in self.rows.items():
            value.setText(f"{getattr(result, key):,}")
            detail.setText(details[key])

        done = state.current_graph_index + 1
        threshold = format_time(ScoringSystem.max_time_threshold(state.difficulty))
        if result.max_time_bonus:
            self.max_time_label.setText(f"✓ MAX TIME BONUS (< {threshold}) · "
                                        f"{state.max_time_bonus_hits}/{done} SO FAR")
            set_text_color(self.max_time_label, UI_GOOD_ON_LIGHT)
        else:
            self.max_time_label.setText(f"✕ MAX TIME BONUS MISSED (< {threshold}) · "
                                        f"×5 RUN BONUS LOST")
            set_text_color(self.max_time_label, UI_MUTED_ON_LIGHT)
        self.provisional_label.setText(f"PROVISIONAL: {state.provisional_score:,}")
        self.show_new_badges()

        self.next_btn.setText("NEXT GRAPH ▶ (ENTER)" if state.has_next_graph()
                              else f"FINISH {state.difficulty} ▶ (ENTER)")
        self.menu_btn.setVisible(result.forfeited)
        self.next_btn.setFocus()

    def show_new_badges(self):
        badges = self.game_state.take_pending_badges()
        self.badges_label.setText("★ BADGE UNLOCKED: " + ", ".join(badge_name(b) for b in badges)
                                  if badges else "")
        self.badges_label.setVisible(bool(badges))

    def confirm_abandon(self) -> bool:
        reply = QMessageBox.question(
            self, "Quit run?",
            "Quit to the menu? Progress is not saved — this difficulty restarts from graph 1.")
        return reply == QMessageBox.StandardButton.Yes

    def on_menu_clicked(self):
        if self.game_state.current_screen != GameScreen.POST_LEVEL or not self.confirm_abandon():
            return
        self.game_state.abandon_run()
        self.main_window.show_screen(GameScreen.MENU)

    def on_next_clicked(self):
        state = self.game_state
        if state.current_screen != GameScreen.POST_LEVEL:
            return
        if state.has_next_graph():
            state.advance_to_next_graph()
            self.main_window.show_screen(GameScreen.PRE_GAME)
        else:
            state.finalize_difficulty()
            self.main_window.show_screen(GameScreen.POST_DIFFICULTY)
