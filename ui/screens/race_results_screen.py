from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QHBoxLayout, QHeaderView,
                               QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from core.constants import (RACE_COLORING, RACE_MODE_NAMES, UI_DANGER_TEXT, UI_GOLD, UI_INNER,
                            UI_LIME)
from core.game_state import GameScreen
from core.planar_run import format_area
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_SECTION, GAP_TIGHT
from ui.widgets.grid_paper import LayoutThumb

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
ROW_HEIGHT = 34
LAYOUT_COLUMN_WIDTH = 250
COLORING_COLUMNS = ["#", "PLAYER", "SOLVED", "SKIPS", "SCORE", ""]
PLANAR_COLUMNS = ["#", "PLAYER", "SOLVED", "AREA", "BOX", ""]
REASONS = {"time": "TIME UP", "host_left": "THE HOST LEFT - THESE ARE THE STANDINGS AT THAT MOMENT"}


class RaceResultsScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.cards: List[QWidget] = []
        self.init_ui()

    @property
    def session(self):
        return self.main_window.multiplayer.session

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = self.fit(make_panel(dark=True), 0.84, 1040, 1200)
        layout = panel_layout(panel)

        self.mode_label = make_label(role="caption")
        layout.addWidget(self.mode_label)
        self.title_label = make_label(role="title")
        layout.addWidget(self.title_label)
        self.reason_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.reason_label)

        tabs = QHBoxLayout()
        tabs.setSpacing(GAP)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.standings_tab = make_button("STANDINGS", variant="tab", small=True)
        self.layouts_tab = make_button("LAYOUTS", variant="tab", small=True)
        for index, tab in enumerate((self.standings_tab, self.layouts_tab)):
            tab.setCheckable(True)
            tab.clicked.connect(lambda _=False, i=index: self.stack.setCurrentIndex(i))
            self.tab_group.addButton(tab, index)
            tabs.addWidget(tab)
        layout.addLayout(tabs)

        self.stack = QStackedWidget()
        self.table = QTableWidget(0, len(COLORING_COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.stack.addWidget(self.table)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack.addWidget(self.scroll)
        layout.addWidget(self.stack, 1)

        self.note_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.note_label)
        layout.addWidget(make_divider(dark=True))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.leave_btn = make_button("LEAVE", self.on_leave_clicked, small=True, icon="back")
        self.lobby_btn = make_button("BACK TO LOBBY", self.on_lobby_clicked, small=True,
                                     icon="play")
        buttons.addWidget(self.leave_btn)
        buttons.addWidget(self.lobby_btn)
        layout.addLayout(buttons)
        outer.addWidget(panel, 1, Qt.AlignmentFlag.AlignHCenter)

    def on_show(self):
        session = self.session
        results = session.results
        mode = results["mode"]
        rows = results["rows"]
        coloring = mode == RACE_COLORING
        self.mode_label.setText(f"MULTIPLAYER | {RACE_MODE_NAMES.get(mode, '')}")
        winner = rows[0] if rows and not rows[0]["dq"] else None
        if winner is None:
            self.title_label.setText("NO WINNER")
        elif winner["id"] == session.my_id:
            self.title_label.setText("YOU WIN!")
        else:
            self.title_label.setText(f"{winner['name']} WINS")
        self.reason_label.setText(REASONS.get(results["reason"], "MATCH OVER"))
        self.fill_table(rows, coloring, session.my_id)
        self.standings_tab.setVisible(not coloring)
        self.layouts_tab.setVisible(not coloring)
        self.standings_tab.setChecked(True)
        self.stack.setCurrentIndex(0)
        if not coloring:
            self.build_cards(results.get("planar", []))
        set_text_color(self.note_label, None)
        self.note_label.setText("DISQUALIFIED: NOTHING SOLVED, OR A SCORE BELOW -10" if coloring
                                else "PLAYERS WHO SOLVED NOTHING ARE DISQUALIFIED")
        self.refresh_buttons()
        (self.lobby_btn if self.lobby_btn.isEnabled() else self.leave_btn).setFocus()

    def refresh_buttons(self):
        session = self.session
        alive = session is not None and session.connected
        self.lobby_btn.setEnabled(alive)

    def on_session_closed(self, reason: str):
        self.note_label.setText(reason)
        set_text_color(self.note_label, UI_DANGER_TEXT)
        self.lobby_btn.setEnabled(False)

    def fill_table(self, rows, coloring: bool, my_id):
        columns = COLORING_COLUMNS if coloring else PLANAR_COLUMNS
        self.table.setRowCount(max(1, len(rows)))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.clearContents()
        for position, row in enumerate(rows):
            status = ("DISQUALIFIED" if row["dq"] else "LEFT" if row["left"]
                      else "YOU" if row["id"] == my_id else "")
            if coloring:
                values = ("-" if row["rank"] is None else row["rank"], row["name"], row["solved"],
                          row["skips"], row["score"], status)
            else:
                values = ("-" if row["rank"] is None else row["rank"], row["name"], row["solved"],
                          format_area(row["area"]), row["box"], status)
            color = (UI_DANGER_TEXT if row["dq"] else UI_LIME if row["id"] == my_id
                     else UI_GOLD if row["rank"] == 1 else UI_INNER if row["left"] else None)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(LEFT)
                if color:
                    item.setForeground(QColor(color))
                self.table.setItem(position, column, item)

    def build_cards(self, summary):
        mine = self.main_window.screens[GameScreen.RACE].my_layouts
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, GAP, 0)
        column.setSpacing(GAP)
        self.cards = []
        for number, entry in enumerate(summary, 1):
            if number > 1:
                column.addWidget(make_divider(dark=True))
            card = self.build_card(number, entry, mine.get(entry["index"]))
            self.cards.append(card)
            column.addWidget(card)
        column.addStretch()
        self.scroll.setWidget(holder)

    def build_card(self, number: int, entry: dict, mine) -> QWidget:
        edges = [(a, b) for a, b in entry["edges"]]
        card = QWidget()
        row = QHBoxLayout(card)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(GAP_SECTION)
        info = QVBoxLayout()
        info.setSpacing(GAP_TIGHT)
        info.addWidget(make_label(f"GRAPH {number}", role="heading", align=LEFT))
        info.addWidget(make_label(f"n = {entry['n']} | EDGES = {len(edges)}", role="caption",
                                  align=LEFT))
        info.addStretch()
        row.addLayout(info, 1)

        program = tuple(entry["program_key"])
        best = tuple(entry["best_key"]) if entry["best_key"] else None
        yours = mine["key"] if mine else None
        least = min(key for key in (program, best, yours) if key is not None)
        row.addLayout(self.layout_column(edges, entry["program_pos"], "PROGRAM", program, least))
        row.addLayout(self.layout_column(edges, entry["best_pos"],
                                         f"BEST: {entry['best_name']}" if best else "BEST PLAYER",
                                         best, least))
        row.addLayout(self.layout_column(edges, mine["pos"] if mine else None, "YOU", yours, least))
        return card

    @staticmethod
    def layout_column(edges, pos, owner: str, key, least) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(2)
        points = [(x, y) for x, y in pos] if pos is not None else None
        column.addWidget(LayoutThumb(edges, points), alignment=Qt.AlignmentFlag.AlignHCenter)
        name = make_label(owner)
        name.setFixedWidth(LAYOUT_COLUMN_WIDTH)
        value = make_label(f"AREA {format_area(key[0])} | BOX {key[1]}" if key else "NOT SOLVED")
        value.setFixedWidth(LAYOUT_COLUMN_WIDTH)
        for label in (name, value):
            set_text_color(label, UI_GOLD if key is not None and tuple(key) == least else None)
            column.addWidget(label)
        return column

    def on_lobby_clicked(self):
        session = self.session
        if session is None or not session.connected:
            return
        self.main_window.show_screen(GameScreen.LOBBY)

    def on_leave_clicked(self):
        self.main_window.multiplayer.leave()
        self.main_window.show_screen(GameScreen.MULTIPLAYER)
