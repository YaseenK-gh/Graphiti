from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from core.constants import PLAYER_NAME_MAX_LEN, UI_GOLD, UI_INNER, UI_LIME
from core.game_state import GameScreen
from core.planar_run import PlanarRecord, format_area
from ui.dialogs import LeaderboardDialog
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_SECTION, GAP_TIGHT
from ui.widgets.grid_paper import LayoutThumb

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
LAYOUT_COLUMN_WIDTH = 300


def layout_text(owner: str, key) -> str:
    return f"{owner}: AREA {format_area(key[0])} | BOX {key[1]}"


class PlanarResultsScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = self.fit(make_panel(dark=True), 0.8, 980, 1160)
        layout = panel_layout(panel)

        layout.addWidget(make_label("TIME UP", role="title"))
        self.summary_label = make_label(role="heading")
        layout.addWidget(self.summary_label)
        layout.addWidget(make_label("RANKED BY GRAPHS SOLVED, THEN SMALLEST AREA, THEN SMALLEST BOX",
                                    role="caption"))
        layout.addWidget(make_divider(dark=True))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll, 1)
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

        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.menu_btn = make_button("MAIN MENU", self.on_menu_clicked, small=True, icon="back")
        self.board_btn = make_button("LEADERBOARD", self.show_leaderboard, variant="dark",
                                     small=True, icon="star")
        self.again_btn = make_button("PLAY AGAIN", self.on_again_clicked, small=True, icon="play")
        for button in (self.menu_btn, self.board_btn, self.again_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        outer.addWidget(panel, 1, Qt.AlignmentFlag.AlignHCenter)

    def on_show(self):
        run = self.game_state.planar_run
        self.summary_label.setText(f"SOLVED: {run.solved} | TOTAL AREA: "
                                   f"{format_area(run.total_area)} | TOTAL BOX: {run.total_box}")
        self.build_cards(run.records)
        can_submit = run.solved > 0 and not run.submitted
        self.name_input.setEnabled(can_submit)
        self.submit_btn.setEnabled(can_submit)
        set_text_color(self.name_error_label, UI_INNER)
        self.name_error_label.setText("" if run.solved else
                                      "SOLVE AT LEAST ONE GRAPH TO GET ON THE BOARD")
        if can_submit:
            self.name_input.setFocus()
        else:
            self.again_btn.setFocus()

    def build_cards(self, records):
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, GAP, 0)
        column.setSpacing(GAP)
        self.cards = []
        for number, record in enumerate(records, 1):
            if number > 1:
                column.addWidget(make_divider(dark=True))
            card = self.build_card(number, record)
            self.cards.append(card)
            column.addWidget(card)
        column.addStretch()
        self.scroll.setWidget(holder)

    def build_card(self, number: int, record: PlanarRecord) -> QWidget:
        puzzle = record.puzzle
        card = QWidget()
        row = QHBoxLayout(card)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(GAP_SECTION)

        info = QVBoxLayout()
        info.setSpacing(GAP_TIGHT)
        info.addWidget(make_label(f"GRAPH {number}", role="heading", align=LEFT))
        info.addWidget(make_label(f"n = {puzzle.n} | EDGES = {len(puzzle.edges)}", role="caption",
                                  align=LEFT))
        if not record.solved:
            verdict, color = "NOT SOLVED", UI_INNER
        elif record.your_key < record.program_key:
            verdict, color = "YOU WERE SMALLER", UI_GOLD
        elif record.your_key == record.program_key:
            verdict, color = "SAME SIZE", UI_LIME
        else:
            verdict, color = "PROGRAM WAS SMALLER", UI_INNER
        verdict_label = make_label(verdict, align=LEFT)
        set_text_color(verdict_label, color)
        info.addWidget(verdict_label)
        info.addStretch()
        row.addLayout(info, 1)

        program_best = not record.solved or record.program_key <= record.your_key
        your_best = record.solved and record.your_key <= record.program_key
        row.addLayout(self.build_layout_column(
            puzzle.edges, record.program_pos, layout_text("PROGRAM", record.program_key),
            program_best))
        row.addLayout(self.build_layout_column(
            puzzle.edges, record.your_pos,
            layout_text("YOU", record.your_key) if record.solved else "YOU: NOT SOLVED",
            your_best))
        return card

    @staticmethod
    def build_layout_column(edges, pos, text: str, best: bool) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(GAP_TIGHT)
        column.addWidget(LayoutThumb(edges, pos), alignment=Qt.AlignmentFlag.AlignHCenter)
        label = make_label(text)
        label.setFixedWidth(LAYOUT_COLUMN_WIDTH)
        set_text_color(label, UI_GOLD if best and pos is not None else None)
        column.addWidget(label)
        return column

    def on_submit_clicked(self):
        rank, error = self.game_state.submit_planar_score(self.name_input.text())
        if error:
            set_text_color(self.name_error_label, None)
            self.name_error_label.setText(error)
            return
        self.name_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        set_text_color(self.name_error_label, UI_LIME)
        self.name_error_label.setText(f"SAVED - RANK #{rank}" if rank
                                      else "SAVED (OUTSIDE THE TOP 100)")

    def show_leaderboard(self):
        LeaderboardDialog(self.game_state.leaderboard_system, self,
                          difficulty=LeaderboardDialog.PLANAR,
                          planar=self.game_state.planar_leaderboard).exec()

    def on_menu_clicked(self):
        self.main_window.show_screen(GameScreen.MENU)

    def on_again_clicked(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self.game_state.start_planar_run()
        finally:
            QApplication.restoreOverrideCursor()
        self.main_window.show_screen(GameScreen.PLANAR_PLAYING)
