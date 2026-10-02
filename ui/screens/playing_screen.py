from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel

from algorithms.solvers import optimal_coloring
from core.constants import (GRAPH_DISPLAY_NAMES, GRAPH_SHORT_NAMES, PALETTE, PALETTE_KEYS, PALETTE_NAMES,
                            SOLUTION_SOLVER_TIMEOUT_MS, UI_BG, UI_BORDER, UI_DANGER_TEXT,
                            UI_GOLD, UI_LIME, UI_LIME_DIM, UI_RED)
from core.game_state import GameScreen
from core.hint_system import HintSystem
from core.scoring import ScoringSystem
from ui.dialogs import PauseDialog
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_TIGHT, PAGE_MARGIN
from ui.overlay import confirm
from ui.widgets.color_palette import ColorPalette
from ui.widgets.graph_canvas import GraphCanvas
from ui.widgets.stats_panel import StatsPanel
from ui.widgets.timer_widget import TimerWidget, format_time

TIER_COLORS = [UI_LIME, UI_GOLD, "#E09040", UI_DANGER_TEXT]
SIDEBAR_FIT = (0.3, 440, 520)
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class PlayingScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.completion_delay_ms = 600
        self.forfeit_linger_ms = 900
        self._completing = False
        self.init_ui()
        self.init_shortcuts()


    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(PAGE_MARGIN)
        main_layout.addWidget(self.build_canvas_panel(), 1)
        main_layout.addWidget(self.build_sidebar())

    def build_canvas_panel(self):
        panel = make_panel()
        layout = panel_layout(panel, compact=True)

        header = QHBoxLayout()
        header.setSpacing(GAP)
        self.header_label = make_label(role="strip", align=LEFT)
        header.addWidget(self.header_label, 1)
        self.chi_badge = make_label(role="badge")
        header.addWidget(self.chi_badge)
        layout.addLayout(header)

        self.canvas = GraphCanvas()
        self.canvas.coloring_changed.connect(self.on_coloring_changed)
        self.canvas.graph_completed.connect(self.on_graph_completed)
        layout.addWidget(self.canvas, 1)

        footer = QHBoxLayout()
        footer.setSpacing(GAP_TIGHT)

        def sample(style: str, w: int = 16, h: int = 16) -> QLabel:
            label = QLabel()
            label.setFixedSize(w, h)
            label.setStyleSheet(style)
            return label

        for swatch, text in ((sample(f"background: #FFFFFF; border: 2px solid {UI_BORDER};"), "UNCOLORED"),
                             (sample(f"background: {PALETTE[4]}; border: 2px solid {UI_BORDER};"), "COLORED"),
                             (sample(f"background: {UI_RED};", 18, 4), "CONFLICT")):
            footer.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignVCenter)
            footer.addWidget(make_label(text, role="caption", align=LEFT))
            footer.addSpacing(GAP)
        footer.addStretch()
        footer.addWidget(make_label("RIGHT-CLICK: ERASE", role="caption", align=RIGHT))
        layout.addLayout(footer)
        return panel

    def build_sidebar(self):
        panel = self.fit(make_panel(dark=True), *SIDEBAR_FIT)
        self.right_panel = panel_layout(panel, compact=True, spacing=GAP_TIGHT)
        right = self.right_panel

        self.mode_label = make_label(role="caption", align=LEFT)
        right.addWidget(self.mode_label)
        self.type_label = make_label(role="heading", align=LEFT)
        right.addWidget(self.type_label)
        self.timer_label = TimerWidget()
        right.addWidget(self.timer_label)
        self.bonus_label = make_label(role="caption", align=LEFT)
        right.addWidget(self.bonus_label)
        right.addWidget(make_divider(dark=True))

        self.stats = StatsPanel()
        right.addWidget(self.stats)
        self.score_label = self.stats.score_label
        self.conflict_label = self.stats.conflict_label
        right.addWidget(make_divider(dark=True))

        right.addWidget(make_label("PALETTE (1-9, 0)", role="caption", align=LEFT))
        self.palette = ColorPalette()
        self.palette.color_selected.connect(self.on_color_selected)
        self.palette.setToolTip("KEYS 1-5: TOP ROW | KEYS 6-9, 0: BOTTOM ROW")
        right.addWidget(self.palette)
        self.color_buttons = self.palette.buttons
        self.active_label = make_label(role="caption", align=LEFT)
        set_text_color(self.active_label, UI_LIME_DIM)
        right.addWidget(self.active_label)

        right.addStretch()
        self.message_label = make_label(role="body", wrap=True, align=LEFT)
        right.addWidget(self.message_label)

        hints_row = QHBoxLayout()
        self.points_label = make_label(role="caption", align=LEFT)
        self.hints_label = make_label(role="caption", align=RIGHT)
        hints_row.addWidget(self.points_label)
        hints_row.addWidget(self.hints_label)
        right.addLayout(hints_row)
        self.hint_btn = make_button("HINT (H)", self.on_buy_hint, variant="dark", small=True)
        right.addWidget(self.hint_btn)

        controls = QHBoxLayout()
        controls.setSpacing(GAP)
        self.reset_btn = make_button("RESET (R)", self.on_reset_requested, small=True)
        self.menu_btn = make_button("MENU (ESC)", self.on_menu_clicked, small=True)
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.menu_btn)
        right.addLayout(controls)
        self.forfeit_btn = make_button("FORFEIT (SHIFT+S)", self.on_forfeit_requested,
                                       variant="danger", small=True)
        right.addWidget(self.forfeit_btn)
        return panel

    def init_shortcuts(self):
        def bind(sequence: str, slot):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        for index, key in enumerate(PALETTE_KEYS):
            bind(key, lambda i=index: self.on_color_selected(i))
        bind("R", self.on_reset_requested)
        bind("H", self.on_buy_hint)
        bind("Escape", self.on_menu_clicked)
        bind("Shift+S", self.on_forfeit_requested)


    def on_show(self):
        state = self.game_state
        self._completing = False
        state.reset_for_new_graph()
        self.canvas.set_graph(state.current_graph, coloring=state.coloring)
        self.palette.set_suggested(None)
        self.on_color_selected(0)
        self.show_message("")
        self.update_ui()
        self.update_timer_display()
        self.canvas.setFocus()

    def on_hide(self):
        self.canvas.stop_animation()
        self.canvas.clear_hint()

    def is_standard(self) -> bool:
        return self.game_state.is_standard()


    def update_ui(self):
        state = self.game_state
        graph = state.current_graph
        if graph is None:
            return
        name = GRAPH_SHORT_NAMES[graph.type]
        self.type_label.setText(name)
        self.chi_badge.setText(f"{graph.chromatic_number} COLORS")
        if self.is_standard():
            progress = f"GRAPH {state.current_graph_index + 1} OF {len(state.graph_queue)}"
            self.mode_label.setText(f"{state.difficulty} | {progress} | n = {graph.n}")
            self.header_label.setText(f"{GRAPH_DISPLAY_NAMES[graph.type]} | n = {graph.n}")
            self.stats.set_score(f"SCORE: {state.provisional_score:,}")
            self.bonus_label.setText(f"MAX TIME BONUS UNDER "
                                     f"{format_time(ScoringSystem.max_time_threshold(state.difficulty))}")
        else:
            self.mode_label.setText(f"FREE MODE | n = {graph.n}")
            self.header_label.setText(f"FREE MODE | {GRAPH_DISPLAY_NAMES[graph.type]} | n = {graph.n}")
            self.stats.set_score(f"EDGES: {len(graph.edges)}")
            self.bonus_label.setText("NO SCORING - TAKE YOUR TIME")
        self.update_conflict_counter()
        self.update_hints_display()

    def update_hints_display(self):
        state = self.game_state
        cost = state.hint_cost()
        if self.is_standard():
            self.points_label.setText(f"POINTS: {state.provisional_score:,}")
        else:
            self.points_label.setText("POINTS: -")
        self.hints_label.setText(f"HINTS USED: {state.hints_used}/{HintSystem.MAX_HINTS_PER_LEVEL}")

        blocked = state.hint_block_reason()
        cooldown = state.hint_cooldown_remaining_ms()
        if cooldown > 0 and state.hints_used < HintSystem.MAX_HINTS_PER_LEVEL:
            text = f"HINT COOLDOWN {cooldown / 1000:.0f}s"
        elif cost:
            text = f"HINT (H) - {cost:,} PTS"
        else:
            text = "FREE HINT (H)"
        if self.hint_btn.text() != text:
            self.hint_btn.setText(text)
        can_buy = blocked is None and not self._completing
        if self.hint_btn.isEnabled() != can_buy:
            self.hint_btn.setEnabled(can_buy)
        tooltip = blocked or f"Reveal a vertex and a safe color for it ({cost:,} points)."
        self.hint_btn.setToolTip(tooltip)

    def update_conflict_counter(self):
        graph = self.game_state.current_graph
        self.stats.set_conflicts(len(self.canvas.conflicts))
        self.stats.set_progress(self.canvas.colored_count(), graph.n, graph.chromatic_number)
        self.stats.set_colors(self.canvas.colors_used(), graph.chromatic_number)

    def update_timer_display(self):
        state = self.game_state
        elapsed = state.get_elapsed_seconds()
        self.timer_label.set_elapsed(elapsed)
        if self.is_standard() and state.difficulty:
            tier = sum(1 for seconds, _ in ScoringSystem.time_tiers(state.difficulty)
                       if elapsed >= seconds)
            self.timer_label.set_color(TIER_COLORS[min(tier, len(TIER_COLORS) - 1)])
        else:
            self.timer_label.set_color(UI_LIME)
        self.update_hints_display()

    def show_message(self, text: str, color: str = UI_BG):
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")


    def on_coloring_changed(self):
        self.update_conflict_counter()
        if self.canvas.hint_vertex is None and self.palette.suggested is not None:
            self.palette.set_suggested(None)

    def on_buy_hint(self):
        if self._completing or self.canvas.is_animating():
            return
        hint, error = self.game_state.buy_hint()
        if error:
            self.show_message(error, UI_DANGER_TEXT)
            self.update_hints_display()
            return
        vertex_id, color = hint
        self.canvas.highlight_vertex(vertex_id, color)
        self.palette.set_suggested(color)
        self.show_hint_popup(vertex_id, color)
        self.update_ui()
        self.canvas.setFocus()

    def show_hint_popup(self, vertex_id: int, color: int):
        recolor = self.canvas.coloring.get(vertex_id) is not None
        verb = "RECOLOR" if recolor else "TRY"
        self.show_message(f"HINT: {verb} THE PULSING VERTEX {PALETTE_NAMES[color]} "
                          f"(KEY {PALETTE_KEYS[color]})", UI_GOLD)

    def on_color_selected(self, color_index: int):
        self.canvas.set_active_color(color_index)
        self.game_state.active_color = color_index
        self.palette.set_active(color_index)
        self.active_label.setText(f"ACTIVE: COLOR {PALETTE_KEYS[color_index]} "
                                  f"({PALETTE_NAMES[color_index]})")

    def on_graph_completed(self):
        if self._completing:
            return
        self._completing = True
        self.canvas.interactive = False
        self.game_state.stop_timer()
        self.update_timer_display()
        colors = self.canvas.colors_used()
        self.show_message("SOLVED!", UI_LIME)
        QTimer.singleShot(self.completion_delay_ms, lambda: self._finish_level(colors, False))

    def _finish_level(self, colors_used: int, forfeited: bool):
        if self.game_state.current_screen != GameScreen.PLAYING:
            return
        self.game_state.record_level_completion(colors_used, forfeited=forfeited)
        next_screen = GameScreen.POST_LEVEL if self.is_standard() else GameScreen.FREE_COMPLETE
        self.main_window.show_screen(next_screen)

    def on_reset_requested(self):
        if self._completing or self.canvas.is_animating():
            return
        if self.is_standard():
            score = self.game_state.provisional_score
            after = ScoringSystem.apply_reset_penalty(score, self.game_state.difficulty)
            if not confirm(self, "Reset level?",
                           f"Restart this graph? You lose 30% of your provisional score "
                           f"({score:,} to {after:,}).", yes="RESET", no="CANCEL", danger=True):
                return
        self.perform_reset()

    def perform_reset(self) -> int:
        lost = self.game_state.apply_level_reset()
        self.canvas.clear_coloring()
        self.palette.set_suggested(None)
        self.update_ui()
        self.update_timer_display()
        self.show_message(f"LEVEL RESET  -{lost:,} PTS" if lost else "LEVEL RESET", UI_GOLD)
        self.canvas.setFocus()
        return lost

    def on_forfeit_requested(self):
        if self._completing or self.canvas.is_animating():
            return
        if self.is_standard():
            if not confirm(self, "Forfeit graph?",
                           "Give up on this graph? It scores 0 points and the solution is revealed.",
                           yes="FORFEIT", no="KEEP PLAYING", danger=True):
                return
        self.perform_forfeit()

    def perform_forfeit(self):
        self._completing = True
        self.game_state.stop_timer()
        graph = self.game_state.current_graph
        solution = optimal_coloring(graph.n, graph.edges, graph.chromatic_number,
                                    timeout_ms=SOLUTION_SOLVER_TIMEOUT_MS)
        colors = len(set(solution.values()))
        self.show_message("FORFEITED - HERE'S A SOLUTION", UI_DANGER_TEXT)
        self.canvas.animate_solution(
            solution,
            on_finished=lambda: QTimer.singleShot(self.forfeit_linger_ms,
                                                  lambda: self._finish_level(colors, True)))

    def on_menu_clicked(self):
        if self._completing or self.canvas.is_animating():
            return
        dialog = self.make_pause_dialog()
        dialog.exec()
        choice = dialog.choice
        if choice == PauseDialog.RESET:
            self.on_reset_requested()
        elif choice == PauseDialog.FORFEIT:
            self.on_forfeit_requested()
        elif choice == PauseDialog.QUIT:
            self.quit_to_menu()
        else:
            self.canvas.setFocus()

    def make_pause_dialog(self):
        return PauseDialog(self, standard_mode=self.is_standard())

    def quit_to_menu(self):
        if self.is_standard():
            if not confirm(self, "Quit run?",
                           "Quit to the menu? Progress is not saved - this difficulty restarts "
                           "from graph 1.", yes="QUIT RUN", no="STAY", danger=True):
                return
            self.game_state.abandon_run()
        else:
            self.game_state.stop_timer()
        self.main_window.show_screen(GameScreen.MENU)
