"""FREE mode: pick any of the 11 graph types and an n."""

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QButtonGroup, QGridLayout, QHBoxLayout, QVBoxLayout

from core.constants import GRAPH_CONSTRAINTS, GRAPH_DESCRIPTIONS, GRAPH_DISPLAY_NAMES, GRAPH_TYPES
from core.game_state import GameScreen
from core.graph_manager import GraphManager
from ui.screens import BaseScreen, make_button, make_divider, make_label, make_panel
from ui.screens.difficulty_select_screen import SHORT_NAMES
from ui.widgets.n_input import NInput, show_error_with_retry
from ui.widgets.pixel import PixelCard


class FreeGraphSelectScreen(BaseScreen):

    COLUMNS = 4

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.selected_graph_type: Optional[str] = None
        self.type_buttons: Dict[str, PixelCard] = {}
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = make_panel()
        panel.setFixedWidth(1040)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(32, 24, 32, 22)
        layout.setSpacing(12)
        layout.addWidget(make_label("FREE MODE — CHOOSE A GRAPH", role="subtitle"))

        grid = QGridLayout()
        grid.setSpacing(12)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, graph_type in enumerate(GRAPH_TYPES):
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            card = PixelCard(SHORT_NAMES.get(graph_type, GRAPH_DISPLAY_NAMES[graph_type]),
                             [f"n = {lo}–{hi}"])
            card.setCheckable(True)
            card.setToolTip(GRAPH_DESCRIPTIONS[graph_type])
            card.clicked.connect(lambda _=False, t=graph_type: self.select_type(t))
            self.group.addButton(card)
            grid.addWidget(card, i // self.COLUMNS, i % self.COLUMNS)
            self.type_buttons[graph_type] = card
        layout.addLayout(grid)

        self.description_label = make_label(role="body", wrap=True)
        self.description_label.setMinimumHeight(52)
        layout.addWidget(self.description_label)
        layout.addWidget(make_divider())

        self.n_widget = NInput()
        self.n_widget.validity_changed.connect(lambda ok: self.start_btn.setEnabled(ok))
        self.n_widget.submitted.connect(self.on_start_clicked)
        layout.addWidget(self.n_widget)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addWidget(make_button("◄ BACK", self.on_back_clicked))
        self.start_btn = make_button("START ▶", self.on_start_clicked)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)
        outer.addWidget(panel)

    def on_show(self):
        self.select_type(self.game_state.selected_graph_type or GRAPH_TYPES[0],
                         self.game_state.selected_n)

    def select_type(self, graph_type: str, n: Optional[int] = None):
        self.selected_graph_type = graph_type
        self.type_buttons[graph_type].setChecked(True)
        self.description_label.setText(GRAPH_DESCRIPTIONS[graph_type])
        lo, hi = GRAPH_CONSTRAINTS[graph_type]
        self.n_widget.set_graph_type(graph_type, n if n is not None and lo <= n <= hi else None)
        self.n_widget.focus()

    def on_start_clicked(self):
        n, error = self.n_widget.validate_and_get_n()
        if error:
            self.n_widget.focus()
            return
        self.start_free_graph(self.selected_graph_type, n)

    def start_free_graph(self, graph_type: str, n: int) -> bool:
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            graph, error = GraphManager.generate_graph_safe(graph_type, n)
        finally:
            QApplication.restoreOverrideCursor()
        if error:
            show_error_with_retry(self, self.n_widget, "Generation Problem", error, current_n=n)
            return False
        state = self.game_state
        state.start_free_mode()
        state.selected_graph_type = graph_type
        state.selected_n = n
        state.begin_graph(graph)
        self.main_window.show_screen(GameScreen.PLAYING)
        return True

    def on_back_clicked(self):
        self.main_window.show_screen(GameScreen.MODE_SELECT)
