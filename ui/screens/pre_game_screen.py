"""STANDARD mode: shows the next graph type and asks for n."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QVBoxLayout

from core.constants import (DIFFICULTY_CONFIG, GRAPH_CONSTRAINTS, GRAPH_DESCRIPTIONS,
                            GRAPH_DISPLAY_NAMES, UI_CAUTION_ON_LIGHT, UI_MUTED_ON_LIGHT)
from core.game_state import GameScreen
from core.graph_manager import GraphManager
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        set_text_color)
from ui.widgets.n_input import NInput, show_error_with_retry


class PreGameScreen(BaseScreen):

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.selected_graph_type = None
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        panel = make_panel()
        panel.setFixedWidth(720)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 30, 40, 28)
        layout.setSpacing(12)

        self.progress_label = make_label(role="caption")
        layout.addWidget(self.progress_label)
        self.type_label = make_label(role="title")
        layout.addWidget(self.type_label)
        self.description_label = make_label(role="body", wrap=True)
        layout.addWidget(self.description_label)
        self.bonus_label = make_label(role="caption")
        layout.addWidget(self.bonus_label)
        self.rule_label = make_label(role="body", wrap=True)
        layout.addWidget(self.rule_label)
        layout.addWidget(make_divider())

        self.n_widget = NInput()
        self.n_widget.validity_changed.connect(lambda ok: self.start_btn.setEnabled(ok))
        self.n_widget.submitted.connect(self.on_start_clicked)
        layout.addWidget(self.n_widget)
        # Plan-compatible aliases.
        self.n_input = self.n_widget.n_input
        self.error_label = self.n_widget.error_label

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.abandon_btn = make_button("◄ ABANDON RUN", self.on_abandon_clicked)
        self.start_btn = make_button("START ▶", self.on_start_clicked)
        buttons.addWidget(self.abandon_btn)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)

        layout.addSpacing(4)
        self.score_label = make_label(role="badge")
        layout.addWidget(self.score_label, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(panel)

    def on_show(self):
        state = self.game_state
        self.selected_graph_type = state.current_graph_type()
        config = DIFFICULTY_CONFIG[state.difficulty]
        self.progress_label.setText(f"{state.difficulty} · GRAPH {state.current_graph_index + 1} "
                                    f"OF {len(state.graph_queue)}")
        self.type_label.setText(GRAPH_DISPLAY_NAMES[self.selected_graph_type])
        self.description_label.setText(GRAPH_DESCRIPTIONS[self.selected_graph_type])
        self.bonus_label.setText(f"+{config['vertex_multiplier']} PTS PER VERTEX — "
                                 f"BIGGER GRAPHS SCORE MORE")
        self.score_label.setText(f"PROVISIONAL SCORE: {state.provisional_score:,}")
        graph_type = self.selected_graph_type
        prev_n = state.previous_n_for(graph_type)
        name = GRAPH_DISPLAY_NAMES[graph_type].upper()
        hi = GRAPH_CONSTRAINTS[graph_type][1]
        if state.locked_n_for(graph_type) is not None:
            rule, color = f"LOCKED AT MAX n = {hi} FOR THE REST OF THIS RUN", UI_CAUTION_ON_LIGHT
        elif prev_n is not None:
            rule, color = (f"LAST {name} LEVEL: n = {prev_n}  →  THIS ONE NEEDS n > {prev_n}",
                           UI_CAUTION_ON_LIGHT)
        else:
            rule, color = (f"EACH LATER {name} LEVEL MUST USE A BIGGER n. "
                           f"PLAYING n = {hi} LOCKS IT THERE."), UI_MUTED_ON_LIGHT
        self.rule_label.setText(rule)
        set_text_color(self.rule_label, color)
        self.n_widget.set_graph_type(graph_type, prev_n=prev_n)
        self.n_widget.focus()

    def validate_and_get_n(self, text: str):
        return self.n_widget.validate_and_get_n(text)

    def on_start_clicked(self):
        """Generate the graph and start playing, with error handling."""
        n, error = self.n_widget.validate_and_get_n()
        if error:
            self.n_widget.focus()
            return
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            graph, error = GraphManager.generate_graph_safe(self.selected_graph_type, n)
        finally:
            QApplication.restoreOverrideCursor()
        if error:
            show_error_with_retry(self, self.n_widget, "Generation Problem", error, current_n=n)
            return
        self.game_state.begin_graph(graph)
        self.main_window.show_screen(GameScreen.PLAYING)

    def on_abandon_clicked(self):
        reply = QMessageBox.question(
            self, "Abandon run?",
            "Quit this difficulty? Progress is not saved — you'll restart from graph 1.")
        if reply == QMessageBox.StandardButton.Yes:
            self.game_state.abandon_run()
            self.main_window.show_screen(GameScreen.MENU)
