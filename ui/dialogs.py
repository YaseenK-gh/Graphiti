"""Modal dialogs: pause menu, How to Play, leaderboard and achievements (dark pixel panels)."""

import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QDialog, QGridLayout, QHBoxLayout,
                               QHeaderView, QScrollArea, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from core.achievements import BADGE_INFO, AchievementSystem
from core.constants import (COLORBLIND_SOLVES, DIFFICULTY_CONFIG, DIFFICULTY_ORDER, HINT_COSTS,
                            LEADERBOARD_TOP_N, MAX_HINTS_PER_LEVEL, UI_BG, UI_BORDER,
                            UI_DANGER_TEXT, UI_GOLD, UI_INK, UI_INNER, UI_LIME)
from core.leaderboard import LeaderboardSystem
from ui import fonts
from ui.screens import make_button, make_divider, make_label, set_text_color
from ui.widgets.pixel import draw_block


class DarkDialog(QDialog):
    """Modal dialog drawn as a dark pixel panel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(34, 28, 34, 26)
        self.layout_.setSpacing(12)

    def paintEvent(self, event):
        draw_block(QPainter(self), self.rect(), UI_INK, UI_BORDER, 4, inner=UI_INNER)


class PauseDialog(DarkDialog):
    """ESC menu. `choice` is one of RESUME / RESET / FORFEIT / QUIT."""

    RESUME, RESET, FORFEIT, QUIT = "resume", "reset", "forfeit", "quit"

    def __init__(self, parent=None, standard_mode: bool = True):
        super().__init__("Paused", parent)
        self.setFixedWidth(460)
        self.choice = self.RESUME
        layout = self.layout_
        layout.addWidget(make_label("PAUSED", role="title"))
        layout.addWidget(make_label("THE CLOCK KEEPS RUNNING", role="caption"))
        layout.addSpacing(6)
        penalty = " (-30%)" if standard_mode else ""
        for text, choice, variant in (("▶ RESUME (ESC)", self.RESUME, "light"),
                                      (f"RESET LEVEL{penalty}", self.RESET, "light"),
                                      ("FORFEIT & SHOW SOLUTION", self.FORFEIT, "danger"),
                                      ("QUIT TO MENU", self.QUIT, "dark")):
            layout.addWidget(make_button(text, lambda _=False, c=choice: self._choose(c),
                                         variant=variant))

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()


def how_to_play_html() -> str:
    def heading(text):
        return (f"<p style=\"font-family:'{fonts.PIXEL}'; font-size:14px; color:{UI_LIME}; "
                f"margin-top:14px;\">{text}</p>")

    def para(text):
        return (f"<p style=\"font-family:'{fonts.TERMINAL}'; font-size:22px; color:{UI_BG};\">"
                f"{text}</p>")

    titles = " · ".join(f"{d}: {c['title']}" for d, c in DIFFICULTY_CONFIG.items())
    return "".join((
        heading("GOAL"),
        para("Color every vertex so that no edge joins two vertices of the same color. Use as few "
             "colors as you can — the fewest possible is the graph's <b>chromatic number χ</b>."),
        heading("CONTROLS"),
        para("<b>Left-click</b> a vertex: paint it with the active color<br>"
             "<b>Right-click</b> a vertex: erase its color<br>"
             "<b>1–9, 0</b>: pick a palette color · <b>H</b>: buy a hint · <b>R</b>: reset level<br>"
             "<b>ESC</b>: pause menu (the clock keeps running) · <b>Shift+S</b>: forfeit and show "
             "the solution<br><b>Mouse wheel</b>: zoom · <b>Middle-drag</b>: pan"),
        para(f"Conflicting edges turn <span style=\"color:{UI_DANGER_TEXT}\"><b>red</b></span>. "
             "The level ends the moment every vertex is colored with no conflicts."),
        heading("STANDARD MODE"),
        para("Three difficulties (EASY 12 graphs, MEDIUM 12, HARD 9). Before each graph you choose "
             "its size <b>n</b>; bigger graphs earn more vertex points. Each graph type appears 3 "
             "times per run, and every later level of a type needs a <b>bigger n</b> than the one "
             "before. Once you play a type at its maximum n, it stays locked there."),
        para("<b>Level score</b> = base + time bonus + n × vertex multiplier + optimality bonus "
             "(+500 for χ colors, +200 for χ+1)."),
        para("<b>Resetting</b> a level costs 30% of your provisional score. Hit the maximum time "
             "bonus on <i>every</i> graph of a difficulty and your score is multiplied by <b>5</b>. "
             "Closing the game mid-difficulty is not saved — you restart from graph 1."),
        heading("HINTS"),
        para(f"Spend provisional points to reveal a vertex and a safe color for it (EASY "
             f"{HINT_COSTS['EASY']}, MEDIUM {HINT_COSTS['MEDIUM']}, HARD {HINT_COSTS['HARD']} "
             f"points). At most {MAX_HINTS_PER_LEVEL} per level, one every 10 seconds, never "
             f"refunded."),
        heading("FREE MODE"),
        para("Practice any of the 11 graph types at any size. No scoring; hints are free."),
        heading("TITLES"),
        para(titles),
    ))


class HowToPlayDialog(DarkDialog):

    def __init__(self, parent=None):
        super().__init__("How to Play", parent)
        self.resize(760, 640)
        self.layout_.addWidget(make_label("HOW TO PLAY", role="title"))
        text = make_label(how_to_play_html(), wrap=True, align=Qt.AlignmentFlag.AlignLeft)
        text.setTextFormat(Qt.TextFormat.RichText)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(text)
        self.layout_.addWidget(scroll, 1)
        self.layout_.addWidget(make_divider(dark=True))
        self.layout_.addWidget(make_button("✕ CLOSE", self.accept, variant="dark", small=True))


class LeaderboardDialog(DarkDialog):
    """Top 10 per difficulty, one tab each."""

    COLUMNS = ["#", "NAME", "SCORE", "GRAPHS", "DATE"]

    def __init__(self, leaderboard: LeaderboardSystem, parent=None, difficulty: str = None):
        super().__init__("Leaderboard", parent)
        self.setMinimumSize(720, 520)
        layout = self.layout_
        layout.addWidget(make_label(f"LEADERBOARD — TOP {LEADERBOARD_TOP_N}", role="title"))

        tabs = QHBoxLayout()
        tabs.setSpacing(10)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.stack = QStackedWidget()
        self.tables = {}
        for i, diff in enumerate(DIFFICULTY_ORDER):
            tab = make_button(diff, variant="tab", small=True)
            tab.setCheckable(True)
            tab.clicked.connect(lambda _=False, index=i: self.stack.setCurrentIndex(index))
            self.tab_group.addButton(tab, i)
            tabs.addWidget(tab)
            table = self._make_table(leaderboard, diff)
            self.tables[diff] = table
            self.stack.addWidget(table)
        layout.addLayout(tabs)
        layout.addWidget(self.stack, 1)
        start = DIFFICULTY_ORDER.index(difficulty) if difficulty in DIFFICULTY_ORDER else 0
        self.tab_group.button(start).setChecked(True)
        self.stack.setCurrentIndex(start)

        layout.addWidget(make_divider(dark=True))
        layout.addWidget(make_button("✕ CLOSE", self.accept, variant="dark", small=True))

    def _make_table(self, leaderboard: LeaderboardSystem, difficulty: str) -> QTableWidget:
        entries = leaderboard.get_top_by_difficulty(difficulty)
        table = QTableWidget(max(1, len(entries)), len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        if not entries:
            table.setSpan(0, 0, 1, len(self.COLUMNS))
            table.setItem(0, 0, self._cell("NO SCORES YET — FINISH A RUN TO GET ON THE BOARD",
                                           UI_INNER))
            return table
        for row, e in enumerate(entries):
            date = datetime.datetime.fromtimestamp(e.timestamp).strftime("%y-%m-%d")
            for col, value in enumerate((row + 1, e.player_name, f"{e.score:,}",
                                         e.graph_count, date)):
                table.setItem(row, col, self._cell(str(value),
                                                   UI_GOLD if row == 0 and col == 0 else None))
        return table

    @staticmethod
    def _cell(text: str, color: str = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(QColor(color))
        return item


class AchievementsDialog(DarkDialog):
    """Every badge (earned or locked), streaks and lifetime solves."""

    def __init__(self, achievements: AchievementSystem, parent=None):
        super().__init__("Achievements", parent)
        self.setMinimumWidth(900)
        layout = self.layout_
        earned = achievements.badges_earned
        layout.addWidget(make_label(f"ACHIEVEMENTS  {len(earned)}/{len(BADGE_INFO)}", role="title"))
        layout.addSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self.badge_labels = {}
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        for row, (badge, (name, how)) in enumerate(BADGE_INFO.items()):
            got = badge in earned
            mark = make_label("★" if got else "☆", role="heading", align=left)
            title = make_label(name, align=left)
            desc = make_label(how, role="body", align=left)
            for label, color in ((mark, UI_LIME if got else UI_INNER),
                                 (title, UI_LIME if got else UI_INNER),
                                 (desc, UI_BG if got else UI_INNER)):
                set_text_color(label, color)
            grid.addWidget(mark, row, 0)
            grid.addWidget(title, row, 1)
            grid.addWidget(desc, row, 2)
            self.badge_labels[badge] = title
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        layout.addWidget(make_divider(dark=True))
        streaks = "  ·  ".join(f"{d}: {achievements.get_streak(d)}" for d in DIFFICULTY_ORDER)
        layout.addWidget(make_label(f"CLEAN-RUN STREAKS — {streaks}"))
        layout.addWidget(make_label(f"GRAPHS SOLVED: {achievements.graphs_solved}"
                                    f" / {COLORBLIND_SOLVES} FOR COLORBLIND", role="caption"))
        layout.addWidget(make_button("✕ CLOSE", self.accept, variant="dark", small=True))
