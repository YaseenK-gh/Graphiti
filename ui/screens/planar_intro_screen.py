from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout

from core.constants import PLANAR_RUN_SECONDS
from core.game_state import GameScreen
from ui.screens import BaseScreen, make_button, make_divider, make_label, make_panel, panel_layout
from ui.styles import GAP


class PlanarIntroScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(), 0.55, 660, 820)
        layout = panel_layout(panel)

        layout.addWidget(make_label("GRAPH DRAWING", role="caption"))
        layout.addWidget(make_label("PLANAR DRAWING", role="title"))
        layout.addWidget(make_label(
            "Every graph starts tangled. Drag its vertices along the grid lines until no two "
            "edges cross. Then shrink the drawing as much as you can and submit it.",
            role="body", wrap=True))
        minutes = PLANAR_RUN_SECONDS // 60
        layout.addWidget(make_label(f"{minutes} MINUTES | NO SKIPS | SOLVE AS MANY AS YOU CAN",
                                    role="caption", wrap=True))
        layout.addWidget(make_label("RANKED BY GRAPHS SOLVED, THEN SMALLEST AREA",
                                    role="caption", wrap=True))
        layout.addWidget(make_divider())

        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.back_btn = make_button("BACK", self.on_back_clicked, icon="back")
        self.start_btn = make_button("START", self.on_start_clicked, icon="play")
        buttons.addWidget(self.back_btn)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)
        outer.addWidget(panel)

    def on_show(self):
        self.start_btn.setFocus()

    def on_start_clicked(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self.game_state.start_planar_run()
        finally:
            QApplication.restoreOverrideCursor()
        self.main_window.show_screen(GameScreen.PLANAR_PLAYING)

    def on_back_clicked(self):
        self.main_window.show_screen(GameScreen.MODE_SELECT)
