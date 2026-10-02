from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QScrollArea, QStackedWidget,
                               QWidget)

from algorithms.planar_puzzle import PlanarPuzzle
from core.constants import (GRAPH_DISPLAY_NAMES, PALETTE_KEYS, PALETTE_NAMES, RACE_COLORING,
                            RACE_DISQUALIFY_BELOW, RACE_MODE_NAMES, UI_BG, UI_DANGER_TEXT,
                            UI_GOLD, UI_INNER, UI_LIME, UI_LIME_DIM, UI_RED)
from core.game_state import Graph, GameScreen
from core.planar_run import format_area
from ui.overlay import confirm
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_TIGHT, PAGE_MARGIN
from ui.widgets.color_palette import ColorPalette
from ui.widgets.graph_canvas import GraphCanvas
from ui.widgets.grid_paper import GridPaper
from ui.widgets.timer_widget import TimerWidget

SIDEBAR_FIT = (0.3, 440, 520)
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
LOW_TIME_SECONDS = 60
LAST_SECONDS = 10
MAX_ROWS = 20


def graph_from(data: dict) -> Graph:
    n = data["n"]
    return Graph(type=data["type"], n=n, vertices=list(range(n)),
                 edges=[(u, v) for u, v in data["edges"]], chromatic_number=data["chi"],
                 layout={v: (float(x), float(y)) for v, (x, y) in enumerate(data["layout"])})


def planar_from(data: dict) -> PlanarPuzzle:
    return PlanarPuzzle(index=data["index"], n=data["n"],
                        edges=[(a, b) for a, b in data["edges"]], cols=data["cols"],
                        rows=data["rows"], start=[(x, y) for x, y in data["start"]], solution=[])


def score_text(row: dict, mode: str) -> str:
    if mode == RACE_COLORING:
        return str(row["score"])
    return f"{row['solved']} | {format_area(row['area'])}"


class Scoreboard(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, GAP_TIGHT, 0)
        grid.setHorizontalSpacing(GAP)
        grid.setVerticalSpacing(0)
        self.cells: List[List[QLabel]] = []
        for row in range(MAX_ROWS):
            labels = [make_label(align=LEFT), make_label(align=LEFT), make_label(align=RIGHT)]
            for column, label in enumerate(labels):
                grid.addWidget(label, row, column)
                label.hide()
            self.cells.append(labels)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(MAX_ROWS, 1)
        self.setWidget(holder)

    def show_rows(self, rows: List[dict], mode: str, my_id: Optional[int]):
        for position, labels in enumerate(self.cells):
            row = rows[position] if position < len(rows) else None
            for label in labels:
                label.setVisible(row is not None)
            if row is None:
                continue
            tag = "DQ" if row["dq"] else "LEFT" if row["left"] else None
            labels[0].setText("-" if row["rank"] is None else str(row["rank"]))
            labels[1].setText(row["name"])
            labels[2].setText(tag or score_text(row, mode))
            color = (UI_LIME if row["id"] == my_id else UI_DANGER_TEXT if row["dq"]
                     else UI_INNER if row["left"] else UI_BG)
            for label in labels:
                set_text_color(label, color)


class RaceScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.puzzle: Optional[dict] = None
        self.waiting = False
        self.out = False
        self.my_layouts: Dict[int, dict] = {}
        self.init_ui()
        self.init_shortcuts()

    @property
    def session(self):
        return self.main_window.multiplayer.session

    def is_coloring(self) -> bool:
        return self.session is not None and self.session.mode == RACE_COLORING

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(PAGE_MARGIN)
        main_layout.addWidget(self.build_board_panel(), 1)
        main_layout.addWidget(self.build_sidebar())

    def build_board_panel(self):
        panel = make_panel()
        layout = panel_layout(panel, compact=True)
        header = QHBoxLayout()
        header.setSpacing(GAP)
        self.header_label = make_label(role="strip", align=LEFT)
        header.addWidget(self.header_label, 1)
        self.badge = make_label(role="badge")
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.boards = QStackedWidget()
        self.canvas = GraphCanvas()
        self.canvas.coloring_changed.connect(self.update_status)
        self.canvas.graph_completed.connect(self.on_graph_completed)
        self.paper = GridPaper()
        self.paper.changed.connect(self.update_status)
        self.boards.addWidget(self.canvas)
        self.boards.addWidget(self.paper)
        layout.addWidget(self.boards, 1)

        footer = QHBoxLayout()
        footer.setSpacing(GAP_TIGHT)
        swatch = QLabel()
        swatch.setFixedSize(18, 4)
        swatch.setStyleSheet(f"background: {UI_RED};")
        footer.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.legend_label = make_label(role="caption", align=LEFT)
        footer.addWidget(self.legend_label)
        footer.addStretch()
        self.help_label = make_label(role="caption", align=RIGHT)
        footer.addWidget(self.help_label)
        layout.addLayout(footer)
        return panel

    def build_sidebar(self):
        panel = self.fit(make_panel(dark=True), *SIDEBAR_FIT)
        right = panel_layout(panel, compact=True, spacing=GAP_TIGHT)

        self.mode_label = make_label(role="caption", align=LEFT)
        right.addWidget(self.mode_label)
        self.graph_label = make_label(role="heading", align=LEFT)
        right.addWidget(self.graph_label)
        self.timer_label = TimerWidget()
        right.addWidget(self.timer_label)
        self.status_label = make_label(align=LEFT)
        right.addWidget(self.status_label)
        self.mine_label = make_label(align=LEFT)
        set_text_color(self.mine_label, UI_LIME_DIM)
        right.addWidget(self.mine_label)
        right.addWidget(make_divider(dark=True))

        self.palette_box = QWidget()
        palette_layout = panel_layout(self.palette_box, spacing=GAP_TIGHT)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.addWidget(make_label("PALETTE (1-9, 0)", role="caption", align=LEFT))
        self.palette = ColorPalette()
        self.palette.color_selected.connect(self.on_color_selected)
        palette_layout.addWidget(self.palette)
        self.active_label = make_label(role="caption", align=LEFT)
        set_text_color(self.active_label, UI_LIME_DIM)
        palette_layout.addWidget(self.active_label)
        palette_layout.addWidget(make_divider(dark=True))
        right.addWidget(self.palette_box)

        right.addWidget(make_label("STANDINGS", role="caption", align=LEFT))
        self.scoreboard = Scoreboard()
        right.addWidget(self.scoreboard, 1)

        self.message_label = make_label(role="body", wrap=True, align=LEFT)
        right.addWidget(self.message_label)
        self.action_btn = make_button("", self.on_action, small=True)
        right.addWidget(self.action_btn)
        controls = QHBoxLayout()
        controls.setSpacing(GAP)
        self.reset_btn = make_button("RESET (R)", self.on_reset, small=True)
        self.leave_btn = make_button("LEAVE (ESC)", self.on_leave_clicked, variant="danger",
                                     small=True)
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.leave_btn)
        right.addLayout(controls)
        for button in (self.action_btn, self.reset_btn, self.leave_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return panel

    def init_shortcuts(self):
        def bind(sequence: str, slot):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        for index, key in enumerate(PALETTE_KEYS):
            bind(key, lambda i=index: self.on_color_selected(i))
        bind("R", self.on_reset)
        bind("Escape", self.on_leave_clicked)
        bind("Return", self.on_enter)
        bind("Enter", self.on_enter)
        bind("S", self.on_skip_key)

    def on_show(self):
        session = self.session
        self.puzzle = None
        self.waiting = False
        self.out = False
        self.my_layouts = {}
        coloring = self.is_coloring()
        self.boards.setCurrentWidget(self.canvas if coloring else self.paper)
        self.palette_box.setVisible(coloring)
        self.mode_label.setText(f"MULTIPLAYER | {RACE_MODE_NAMES.get(session.mode, '')}")
        self.legend_label.setText("CONFLICT" if coloring else "CROSSING")
        self.help_label.setText("RIGHT-CLICK: ERASE | S: SKIP" if coloring
                                else "DRAG ALONG THE LINES | ARROWS: STEP")
        self.header_label.setText("GET READY")
        self.badge.setText("")
        self.graph_label.setText("")
        self.show_message("")
        self.on_color_selected(0)
        self.set_board_locked(True)
        self.update_standings()
        self.tick()
        if session.puzzle is not None:
            self.load_puzzle(session.puzzle)

    def on_hide(self):
        self.canvas.stop_animation()

    def set_board_locked(self, locked: bool):
        self.canvas.interactive = not locked
        self.paper.locked = locked
        self.update_buttons()

    def board_locked(self) -> bool:
        return self.paper.locked if not self.is_coloring() else not self.canvas.interactive

    def load_puzzle(self, data: dict):
        self.puzzle = data
        self.waiting = False
        number = data["index"] + 1
        self.graph_label.setText(f"GRAPH {number}")
        if self.is_coloring():
            graph = graph_from(data)
            self.canvas.set_graph(graph)
            self.header_label.setText(f"GRAPH {number} | {GRAPH_DISPLAY_NAMES[graph.type]} | "
                                      f"n = {graph.n}")
            self.badge.setText(f"{graph.chromatic_number} COLORS")
            self.canvas.setFocus()
        else:
            puzzle = planar_from(data)
            self.paper.load(puzzle)
            self.header_label.setText(f"GRAPH {number} | n = {puzzle.n} | "
                                      f"EDGES = {len(puzzle.edges)}")
            self.paper.setFocus()
        self.set_board_locked(self.out)
        self.update_status()

    def my_row(self) -> Optional[dict]:
        return self.session.my_row() if self.session is not None else None

    def skip_cost(self) -> int:
        row = self.my_row()
        return (row["skips"] if row else 0) + 1

    def update_status(self):
        if self.puzzle is None or self.session is None:
            return
        if self.is_coloring():
            graph = self.canvas.graph
            conflicts = len(self.canvas.conflicts)
            text = f"COLORED: {self.canvas.colored_count()}/{graph.n}"
            text += f" | {conflicts} CONFLICT{'S' if conflicts != 1 else ''}" if conflicts else ""
            self.status_label.setText(text)
            set_text_color(self.status_label, UI_DANGER_TEXT if conflicts else UI_BG)
        else:
            key = self.paper.measure()
            if key is None:
                self.badge.setText(f"{len(self.paper.bad)} CROSSING")
                self.status_label.setText(f"CROSSING EDGES: {len(self.paper.bad)}")
                set_text_color(self.status_label, UI_DANGER_TEXT)
            else:
                self.badge.setText("PLANAR")
                self.status_label.setText(f"AREA: {format_area(key[0])} | BOX: {key[1]}")
                set_text_color(self.status_label, UI_LIME)
        self.update_buttons()

    def update_buttons(self):
        if self.session is None:
            return
        playing = self.puzzle is not None and not self.out and not self.waiting
        if self.is_coloring():
            self.action_btn.setText(f"SKIP (S)  -{self.skip_cost()}")
            self.action_btn.set_variant("dark")
            self.action_btn.setEnabled(playing)
        else:
            self.action_btn.setText("SUBMIT (ENTER)")
            self.action_btn.set_variant("light")
            self.action_btn.setEnabled(playing and self.paper.is_planar())
        self.reset_btn.setEnabled(playing)

    def update_standings(self):
        session = self.session
        if session is None:
            return
        self.scoreboard.show_rows(session.rows, session.mode, session.my_id)
        row = self.my_row()
        if row is not None:
            if self.is_coloring():
                self.mine_label.setText(f"SOLVED: {row['solved']} | SKIPS: {row['skips']} | "
                                        f"SCORE: {row['score']}")
            else:
                self.mine_label.setText(f"SOLVED: {row['solved']} | AREA: "
                                        f"{format_area(row['area'])} | BOX: {row['box']}")
            if row["dq"] and not self.out:
                self.disqualify()
        self.update_buttons()

    def tick(self):
        session = self.session
        if session is None:
            return
        left = session.remaining()
        self.timer_label.set_elapsed(left + 0.999 if left > 0 else 0)
        self.timer_label.set_color(UI_DANGER_TEXT if left <= LAST_SECONDS
                                   else UI_GOLD if left <= LOW_TIME_SECONDS else UI_LIME)

    def show_message(self, text: str, color: str = UI_BG):
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")

    def on_color_selected(self, color_index: int):
        self.canvas.set_active_color(color_index)
        self.palette.set_active(color_index)
        self.active_label.setText(f"ACTIVE: COLOR {PALETTE_KEYS[color_index]} "
                                  f"({PALETTE_NAMES[color_index]})")

    def on_graph_completed(self):
        if self.waiting or self.out or self.puzzle is None or not self.is_coloring():
            return
        data = [self.canvas.coloring[v] for v in range(self.puzzle["n"])]
        self.send(lambda: self.session.submit(self.puzzle["index"], data), "SOLVED!")

    def send(self, action, message: str):
        self.waiting = True
        self.set_board_locked(True)
        self.show_message(message, UI_LIME)
        action()

    def on_action(self):
        if self.is_coloring():
            self.on_skip()
        else:
            self.on_submit_planar()

    def on_enter(self):
        if not self.is_coloring():
            self.on_submit_planar()

    def on_skip_key(self):
        if self.is_coloring():
            self.on_skip()

    def on_submit_planar(self):
        if self.waiting or self.out or self.puzzle is None or self.is_coloring():
            return
        key = self.paper.measure()
        if key is None:
            self.show_message("REMOVE EVERY CROSSING FIRST", UI_DANGER_TEXT)
            return
        index = self.puzzle["index"]
        self.my_layouts[index] = {"pos": list(self.paper.pos), "key": key}
        data = [list(p) for p in self.paper.pos]
        self.send(lambda: self.session.submit(index, data),
                  f"GRAPH {index + 1} SENT: AREA {format_area(key[0])} | BOX {key[1]}")

    def confirm_fatal_skip(self) -> bool:
        return confirm(self, "Skip and be disqualified?",
                       f"This skip costs {self.skip_cost()} and takes your score below "
                       f"{RACE_DISQUALIFY_BELOW}. You will be out of the match.",
                       yes="SKIP ANYWAY", no="KEEP PLAYING", danger=True)

    def on_skip(self):
        if self.waiting or self.out or self.puzzle is None or not self.is_coloring():
            return
        row = self.my_row()
        score = row["score"] if row else 0
        if score - self.skip_cost() < RACE_DISQUALIFY_BELOW and not self.confirm_fatal_skip():
            return
        if self.session is None or self.puzzle is None:
            return
        cost = self.skip_cost()
        self.send(lambda: self.session.skip(self.puzzle["index"]), f"SKIPPED  -{cost}")

    def on_result(self, message: dict):
        if message.get("ok"):
            if message.get("dq"):
                self.disqualify()
            return
        self.waiting = False
        if message.get("action") == "submit" and not self.is_coloring():
            self.my_layouts.pop(message.get("index"), None)
        self.set_board_locked(self.out)
        self.show_message(str(message.get("reason") or "NOT ACCEPTED").upper(), UI_DANGER_TEXT)

    def disqualify(self):
        self.out = True
        self.waiting = False
        self.set_board_locked(True)
        self.show_message("DISQUALIFIED - YOU CAN STILL WATCH THE STANDINGS", UI_DANGER_TEXT)

    def on_match_ended(self):
        self.set_board_locked(True)

    def on_reset(self):
        if self.waiting or self.out or self.puzzle is None:
            return
        if self.is_coloring():
            self.canvas.clear_coloring()
            self.canvas.setFocus()
        else:
            self.paper.reset()
            self.paper.setFocus()
        self.show_message("BACK TO THE START", UI_GOLD)

    def confirm_leave(self) -> bool:
        host = self.session is not None and self.session.is_host
        return confirm(self, "Leave match?",
                       "You are the host. Leaving ends the match for everyone." if host
                       else "Leave the match? You cannot come back in.",
                       yes="LEAVE", no="STAY", danger=True)

    def on_leave_clicked(self):
        if not self.confirm_leave():
            return
        if self.game_state.current_screen != GameScreen.RACE:
            return
        self.main_window.multiplayer.leave()
        self.main_window.show_screen(GameScreen.MULTIPLAYER)
