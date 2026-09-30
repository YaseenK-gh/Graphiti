"""Main game screen: interactive graph, timer, palette, stats and controls."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout

from algorithms.solvers import optimal_coloring
from core.constants import (GRAPH_DISPLAY_NAMES, PALETTE, PALETTE_KEYS, PALETTE_NAMES,
                            SOLUTION_SOLVER_TIMEOUT_MS, UI_BG, UI_BORDER, UI_DANGER_TEXT, UI_FIELD,
                            UI_GOLD, UI_INK, UI_INNER, UI_LIME, UI_LIME_DIM, UI_RED)
from core.game_state import GameScreen
from core.hint_system import HintSystem
from core.scoring import ScoringSystem
from ui.dialogs import PauseDialog
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        set_text_color)
from ui.widgets.color_palette import ColorPalette
from ui.widgets.graph_canvas import GraphCanvas
from ui.widgets.stats_panel import StatsPanel
from ui.widgets.timer_widget import TimerWidget, format_time

# Timer color per time-bonus tier: max bonus, then progressively worse.
TIER_COLORS = [UI_LIME, UI_GOLD, "#E09040", UI_DANGER_TEXT]
SIDEBAR_WIDTH = 400
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class PlayingScreen(BaseScreen):
    """Main game playing screen with graph visualization."""

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.completion_delay_ms = 600      # Pause on the solved graph before moving on.
        self.forfeit_linger_ms = 900        # Show the revealed solution before moving on.
        self._completing = False
        self.init_ui()
        self.init_shortcuts()

    # ─── Construction ─────────────────────────────────────────────────────────

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        main_layout.addWidget(self.build_canvas_panel(), 1)

        side = QVBoxLayout()
        side.setSpacing(12)
        side.addWidget(self.build_sidebar(), 1)
        side.addWidget(self.build_legend())
        main_layout.addLayout(side)

    def build_canvas_panel(self):
        panel = make_panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.header_label = QLabel()
        self.header_label.setStyleSheet(f"background: {UI_FIELD}; color: {UI_INK}; font-size: 11px; "
                                        f"border: 3px solid {UI_BORDER}; padding: 8px 10px;")
        header.addWidget(self.header_label, 1)
        self.chi_badge = make_label(role="badge")
        header.addWidget(self.chi_badge)
        layout.addLayout(header)

        self.canvas = GraphCanvas()
        self.canvas.coloring_changed.connect(self.on_coloring_changed)
        self.canvas.graph_completed.connect(self.on_graph_completed)
        layout.addWidget(self.canvas, 1)

        footer = QHBoxLayout()
        footer.addWidget(make_label("LEFT-CLICK: COLOR · RIGHT-CLICK: ERASE", role="caption",
                                    align=LEFT))
        footer.addStretch()
        footer.addWidget(make_label("WHEEL: ZOOM · MIDDLE-DRAG: PAN", role="caption", align=RIGHT))
        layout.addLayout(footer)
        return panel

    def build_sidebar(self):
        panel = make_panel(dark=True)
        panel.setFixedWidth(SIDEBAR_WIDTH)
        self.right_panel = QVBoxLayout(panel)
        right = self.right_panel
        right.setContentsMargins(22, 18, 22, 18)
        right.setSpacing(7)

        self.mode_label = make_label(align=LEFT)
        set_text_color(self.mode_label, UI_INNER)
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
        # Plan-compatible aliases.
        self.score_label = self.stats.score_label
        self.conflict_label = self.stats.conflict_label
        right.addWidget(make_divider(dark=True))

        right.addWidget(make_label("PALETTE (1–9, 0)", role="caption", align=LEFT))
        self.palette = ColorPalette()
        self.palette.color_selected.connect(self.on_color_selected)
        right.addWidget(self.palette)
        self.color_buttons = self.palette.buttons
        self.active_label = make_label(role="caption", align=LEFT)
        set_text_color(self.active_label, UI_LIME_DIM)
        right.addWidget(self.active_label)

        right.addStretch()
        self.message_label = make_label(role="body", wrap=True, align=LEFT)
        self.message_label.setMinimumHeight(46)
        right.addWidget(self.message_label)

        hints_row = QHBoxLayout()
        self.points_label = make_label(role="caption", align=LEFT)
        self.hints_label = make_label(role="caption", align=RIGHT)
        hints_row.addWidget(self.points_label)
        hints_row.addWidget(self.hints_label)
        right.addLayout(hints_row)
        self.hint_btn = make_button("BUY HINT (H)", self.on_buy_hint, variant="dark", small=True)
        right.addWidget(self.hint_btn)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.reset_btn = make_button("RESET (R)", self.on_reset_requested, small=True)
        self.menu_btn = make_button("MENU (ESC)", self.on_menu_clicked, small=True)
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.menu_btn)
        right.addLayout(controls)
        self.forfeit_btn = make_button("FORFEIT (SHIFT+S)", self.on_forfeit_requested,
                                       variant="danger", small=True)
        right.addWidget(self.forfeit_btn)
        return panel

    def build_legend(self):
        panel = make_panel(dark=True)
        panel.setFixedWidth(SIDEBAR_WIDTH)
        grid = QGridLayout(panel)
        grid.setContentsMargins(22, 14, 22, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        def sample(style: str, w: int = 16, h: int = 16) -> QLabel:
            label = QLabel()
            label.setFixedSize(w, h)
            label.setStyleSheet(style)
            return label

        items = (
            (sample(f"background: {PALETTE[4]}; border: 2px solid {UI_BORDER};"), "COLORED OK"),
            (sample(f"background: #FFFFFF; border: 2px solid {UI_BORDER};"), "UNCOLORED"),
            (sample(f"background: {UI_RED};", 18, 4), "CONFLICT EDGE"),
        )
        grid.addWidget(make_label("LEGEND", role="caption", align=LEFT), 0, 0, 1, 4)
        for i, (swatch, text) in enumerate(items):
            row, col = 1 + i // 2, (i % 2) * 2
            grid.addWidget(swatch, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
            label = make_label(text, role="caption", align=LEFT)
            set_text_color(label, UI_LIME_DIM)
            grid.addWidget(label, row, col + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
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

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def on_show(self):
        """Load the prepared graph and start the clock."""
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

    # ─── Display ──────────────────────────────────────────────────────────────

    def update_ui(self):
        """Update all labels from the game state."""
        state = self.game_state
        graph = state.current_graph
        if graph is None:
            return
        name = GRAPH_DISPLAY_NAMES[graph.type]
        self.type_label.setText(f"{name} · n = {graph.n}")
        # Long names drop to a smaller size so they fit the sidebar on one line.
        size = 16 if len(self.type_label.text()) <= 21 else 12
        self.type_label.setStyleSheet(f"font-size: {size}px;")
        self.chi_badge.setText(f"χ = {graph.chromatic_number}")
        if self.is_standard():
            progress = f"GRAPH {state.current_graph_index + 1} OF {len(state.graph_queue)}"
            self.mode_label.setText(f"{state.difficulty} · {progress}")
            self.header_label.setText(f"{state.difficulty} · {progress} · {name} · n={graph.n}")
            self.stats.set_score(f"SCORE: {state.provisional_score:,}")
            self.bonus_label.setText(f"MAX TIME BONUS UNDER "
                                     f"{format_time(ScoringSystem.max_time_threshold(state.difficulty))}")
        else:
            self.mode_label.setText("FREE MODE · PRACTICE")
            self.header_label.setText(f"FREE · {name} · n={graph.n}")
            self.stats.set_score(f"EDGES: {len(graph.edges)}")
            self.bonus_label.setText("NO SCORING — TAKE YOUR TIME")
        self.update_conflict_counter()
        self.update_hints_display()

    def update_hints_display(self):
        """Points, hints used, and the buy button (disabled when unaffordable/maxed/cooling down)."""
        state = self.game_state
        cost = state.hint_cost()
        if self.is_standard():
            self.points_label.setText(f"POINTS: {state.provisional_score:,}")
        else:
            self.points_label.setText("POINTS: —")
        self.hints_label.setText(f"HINTS USED: {state.hints_used}/{HintSystem.MAX_HINTS_PER_LEVEL}")

        blocked = state.hint_block_reason()
        cooldown = state.hint_cooldown_remaining_ms()
        if cooldown > 0 and state.hints_used < HintSystem.MAX_HINTS_PER_LEVEL:
            text = f"HINT COOLDOWN {cooldown / 1000:.0f}s"
        elif cost:
            text = f"BUY HINT (H) — {cost:,} PTS"
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
        """Refresh the timer (called every 100ms by the main window)."""
        state = self.game_state
        elapsed = state.get_elapsed_seconds()
        self.timer_label.set_elapsed(elapsed)
        if self.is_standard() and state.difficulty:
            tier = sum(1 for seconds, _ in ScoringSystem.time_tiers(state.difficulty)
                       if elapsed >= seconds)
            self.timer_label.set_color(TIER_COLORS[min(tier, len(TIER_COLORS) - 1)])
        else:
            self.timer_label.set_color(UI_LIME)
        self.update_hints_display()  # Keeps the cooldown countdown live.

    def show_message(self, text: str, color: str = UI_BG):
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")

    # ─── Interaction ──────────────────────────────────────────────────────────

    def on_coloring_changed(self):
        self.update_conflict_counter()
        if self.canvas.hint_vertex is None and self.palette.suggested is not None:
            self.palette.set_suggested(None)  # The hinted vertex has been colored.

    def on_buy_hint(self):
        """Purchase a hint (with cooldown/points/max checks) and show it on the canvas."""
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
        """Every vertex colored, no conflicts: stop the clock and move on shortly."""
        if self._completing:
            return
        self._completing = True
        self.canvas.interactive = False
        self.game_state.stop_timer()
        self.update_timer_display()
        colors = self.canvas.colors_used()
        self.show_message("✓ SOLVED!", UI_LIME)
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
            reply = QMessageBox.question(
                self, "Reset level?",
                "Restart this graph? You lose 30% of your provisional score "
                f"({self.game_state.provisional_score:,} → "
                f"{ScoringSystem.apply_reset_penalty(self.game_state.provisional_score, self.game_state.difficulty):,}).")
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.perform_reset()

    def perform_reset(self) -> int:
        """Clear the graph and restart the timer (applies the reset penalty in STANDARD)."""
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
            reply = QMessageBox.question(
                self, "Forfeit graph?",
                "Give up on this graph? It scores 0 points and the solution is revealed.")
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.perform_forfeit()

    def perform_forfeit(self):
        """Reveal an optimal coloring, then record the level as forfeited."""
        self._completing = True
        self.game_state.stop_timer()
        graph = self.game_state.current_graph
        solution = optimal_coloring(graph.n, graph.edges, graph.chromatic_number,
                                    timeout_ms=SOLUTION_SOLVER_TIMEOUT_MS)
        colors = len(set(solution.values()))
        self.show_message("FORFEITED — HERE'S A SOLUTION", UI_DANGER_TEXT)
        self.canvas.animate_solution(
            solution,
            on_finished=lambda: QTimer.singleShot(self.forfeit_linger_ms,
                                                  lambda: self._finish_level(colors, True)))

    def on_menu_clicked(self):
        """Pause menu. The clock keeps running while it's open."""
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
            reply = QMessageBox.question(
                self, "Quit run?",
                "Quit to the menu? Progress is not saved — this difficulty restarts from graph 1.")
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.game_state.abandon_run()
        else:
            self.game_state.stop_timer()
        self.main_window.show_screen(GameScreen.MENU)
