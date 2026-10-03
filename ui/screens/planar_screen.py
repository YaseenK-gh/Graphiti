from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel

from core.constants import (PLANAR_SEARCH_SLICE_SECONDS, UI_BG, UI_DANGER_TEXT, UI_GOLD, UI_LIME,
                            UI_LIME_DIM, UI_RED)
from core.game_state import GameScreen
from core.planar_run import format_area
from ui.dialogs import PauseDialog
from ui.overlay import confirm
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_TIGHT, PAGE_MARGIN
from ui.widgets.grid_paper import GridPaper
from ui.widgets.timer_widget import TimerWidget

SIDEBAR_FIT = (0.3, 440, 520)
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
LOW_TIME_SECONDS = 60
LAST_SECONDS = 10


class PlanarScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self._modal = False
        self.init_ui()
        self.init_shortcuts()

    @property
    def run(self):
        return self.game_state.planar_run

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(PAGE_MARGIN)
        main_layout.addWidget(self.build_paper_panel(), 1)
        main_layout.addWidget(self.build_sidebar())

    def build_paper_panel(self):
        panel = make_panel()
        layout = panel_layout(panel, compact=True)

        header = QHBoxLayout()
        header.setSpacing(GAP)
        self.header_label = make_label(role="strip", align=LEFT)
        header.addWidget(self.header_label, 1)
        self.state_badge = make_label(role="badge")
        header.addWidget(self.state_badge)
        layout.addLayout(header)

        self.paper = GridPaper()
        self.paper.changed.connect(self.update_status)
        layout.addWidget(self.paper, 1)

        footer = QHBoxLayout()
        footer.setSpacing(GAP_TIGHT)
        swatch = QLabel()
        swatch.setFixedSize(18, 4)
        swatch.setStyleSheet(f"background: {UI_RED};")
        footer.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(make_label("CROSSING", role="caption", align=LEFT))
        footer.addStretch()
        footer.addWidget(make_label("DRAG OR ARROWS: MOVE | WASD: SWITCH", role="caption",
                                    align=RIGHT))
        layout.addLayout(footer)
        return panel

    def build_sidebar(self):
        panel = self.fit(make_panel(dark=True), *SIDEBAR_FIT)
        right = panel_layout(panel, compact=True, spacing=GAP_TIGHT)

        right.addWidget(make_label("PLANAR DRAWING", role="caption", align=LEFT))
        self.graph_label = make_label(role="heading", align=LEFT)
        right.addWidget(self.graph_label)
        self.timer_label = TimerWidget()
        right.addWidget(self.timer_label)
        self.size_label = make_label(role="caption", align=LEFT)
        right.addWidget(self.size_label)
        right.addWidget(make_divider(dark=True))

        self.crossing_label = make_label(align=LEFT)
        self.area_label = make_label(align=LEFT)
        self.box_label = make_label(align=LEFT)
        for label in (self.crossing_label, self.area_label, self.box_label):
            right.addWidget(label)
        right.addWidget(make_divider(dark=True))

        self.solved_label = make_label(align=LEFT)
        self.total_area_label = make_label(align=LEFT)
        self.total_box_label = make_label(align=LEFT)
        for label in (self.solved_label, self.total_area_label, self.total_box_label):
            set_text_color(label, UI_LIME_DIM)
            right.addWidget(label)

        right.addStretch()
        self.message_label = make_label(role="body", wrap=True, align=LEFT)
        right.addWidget(self.message_label)

        self.submit_btn = make_button("SUBMIT (ENTER)", self.on_submit, small=True, icon="play")
        right.addWidget(self.submit_btn)
        controls = QHBoxLayout()
        controls.setSpacing(GAP)
        self.reset_btn = make_button("RESET (R)", self.on_reset, small=True)
        self.menu_btn = make_button("MENU (ESC)", self.on_menu_clicked, small=True)
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.menu_btn)
        right.addLayout(controls)
        for button in (self.submit_btn, self.reset_btn, self.menu_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return panel

    def init_shortcuts(self):
        for sequence, slot in (("Return", self.on_submit), ("Enter", self.on_submit),
                               ("R", self.on_reset), ("Escape", self.on_menu_clicked)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

    def on_show(self):
        self._modal = False
        self.paper.locked = False
        self.show_message("")
        self.load_current()
        self.tick()
        self.paper.setFocus()

    def load_current(self):
        self.paper.load(self.run.current.puzzle)
        self.update_ui()

    def update_ui(self):
        run = self.run
        puzzle = run.current.puzzle
        number = len(run.records)
        self.graph_label.setText(f"GRAPH {number}")
        self.header_label.setText(f"PLANAR DRAWING | GRAPH {number} | n = {puzzle.n}")
        self.size_label.setText(f"n = {puzzle.n} | EDGES = {len(puzzle.edges)}")
        self.solved_label.setText(f"SOLVED: {run.solved}")
        self.total_area_label.setText(f"TOTAL AREA: {format_area(run.total_area)}")
        self.total_box_label.setText(f"TOTAL BOX: {run.total_box}")
        self.update_status()

    def update_status(self):
        crossing = len(self.paper.bad)
        key = self.paper.measure()
        if key is None:
            self.state_badge.setText(f"{crossing} CROSSING")
            self.crossing_label.setText(f"CROSSING EDGES: {crossing}")
            set_text_color(self.crossing_label, UI_DANGER_TEXT)
            self.area_label.setText("AREA: -")
            self.box_label.setText("BOX: -")
        else:
            self.state_badge.setText("PLANAR")
            self.crossing_label.setText("NO CROSSINGS")
            set_text_color(self.crossing_label, UI_LIME)
            self.area_label.setText(f"AREA: {format_area(key[0])}")
            self.box_label.setText(f"BOX: {key[1]}")
        ready = key is not None and not self.paper.locked
        if self.submit_btn.isEnabled() != ready:
            self.submit_btn.setEnabled(ready)

    def show_message(self, text: str, color: str = UI_BG):
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")

    def tick(self):
        run = self.run
        if run is None:
            return
        left = run.remaining()
        self.timer_label.set_elapsed(left + 0.999 if left > 0 else 0)
        self.timer_label.set_color(UI_DANGER_TEXT if left <= LAST_SECONDS
                                   else UI_GOLD if left <= LOW_TIME_SECONDS else UI_LIME)
        if run.time_up():
            if not self._modal:
                self.finish()
            return
        run.improve(PLANAR_SEARCH_SLICE_SECONDS)

    def finish(self):
        if self.game_state.current_screen != GameScreen.PLANAR_PLAYING:
            return
        self.paper.locked = True
        self.main_window.show_screen(GameScreen.PLANAR_RESULTS)

    def on_submit(self):
        run = self.run
        if run is None or self.paper.locked or self._modal:
            return
        number = len(run.records)
        key = run.submit(self.paper.pos)
        if key is None:
            if run.time_up():
                self.finish()
            else:
                self.show_message("REMOVE EVERY CROSSING FIRST", UI_DANGER_TEXT)
            return
        self.load_current()
        self.show_message(f"GRAPH {number} DONE: AREA {format_area(key[0])} | BOX {key[1]}",
                          UI_LIME)
        self.paper.setFocus()

    def on_reset(self):
        if self.paper.locked or self._modal:
            return
        self.paper.reset()
        self.show_message("BACK TO THE START", UI_GOLD)
        self.paper.setFocus()

    def on_menu_clicked(self):
        if self.paper.locked or self._modal:
            return
        self._modal = True
        try:
            dialog = self.make_pause_dialog()
            dialog.exec()
            choice = dialog.choice
            quit_run = choice == PauseDialog.QUIT and self.confirm_quit()
        finally:
            self._modal = False
        if quit_run:
            self.game_state.planar_run = None
            self.main_window.show_screen(GameScreen.MENU)
            return
        if self.run.time_up():
            self.finish()
            return
        if choice == PauseDialog.RESET:
            self.on_reset()
        self.paper.setFocus()

    def make_pause_dialog(self):
        return PauseDialog(self, standard_mode=False, allow_forfeit=False)

    def confirm_quit(self) -> bool:
        return confirm(self, "Quit run?", "Quit to the menu? This run will not be saved.",
                       yes="QUIT RUN", no="STAY", danger=True)
