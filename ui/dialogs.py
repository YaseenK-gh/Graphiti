import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QGridLayout, QHBoxLayout,
                               QHeaderView, QScrollArea, QSlider, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QLabel)

from core.achievements import BADGE_INFO, AchievementSystem
from core.constants import (COLORBLIND_SOLVES, DIFFICULTY_CONFIG, DIFFICULTY_ORDER,
                            GRAPH_DISPLAY_NAMES, HINT_COSTS, LEADERBOARD_TOP_N,
                            MAX_HINTS_PER_LEVEL, PALETTE, PALETTE_KEYS, PALETTE_NAMES, UI_BG,
                            UI_DANGER_TEXT, UI_GOLD, UI_INNER, UI_LIME)
from core.leaderboard import LeaderboardSystem
from ui import fonts
from ui.audio import track_name
from ui.overlay import Overlay
from ui.widgets.pixel import icon_pixmap
from ui.widgets.pixel import icon_pixmap
from ui.screens import make_button, make_divider, make_label, set_text_color
from ui.styles import GAP, GAP_TIGHT, LINE_SPACING_CSS, SIZE_SUBTITLE, size_body

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class PauseDialog(Overlay):
    RESUME, RESET, FORFEIT, QUIT = "resume", "reset", "forfeit", "quit"

    def __init__(self, parent=None, standard_mode: bool = True):
        super().__init__(parent, width_fraction=0.38, min_width=520, max_width=600)
        self.choice = self.RESUME
        layout = self.layout_
        layout.addWidget(make_label("PAUSED", role="title"))
        layout.addWidget(make_label("THE CLOCK KEEPS RUNNING", role="caption"))
        layout.addSpacing(GAP_TIGHT)
        penalty = " (-30%)" if standard_mode else ""
        for text, choice, variant, icon in (("RESUME (ESC)", self.RESUME, "light", "play"),
                                            (f"RESET LEVEL{penalty}", self.RESET, "light", None),
                                            ("FORFEIT & SHOW SOLUTION", self.FORFEIT, "danger", None),
                                            ("QUIT TO MENU", self.QUIT, "dark", "back")):
            layout.addWidget(make_button(text, lambda _=False, c=choice: self._choose(c),
                                         variant=variant, icon=icon))

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()


def _hl(text: str) -> str:
    return f'<span style="color:{UI_LIME}">{text}</span>'


def guide_html() -> str:
    def heading(text):
        return (f"<p style=\"font-family:'{fonts.PIXEL}'; font-size:{SIZE_SUBTITLE}px; "
                f"color:{UI_LIME}; margin-top:18px; margin-bottom:6px;\">{text}</p>")

    def para(text):
        return (f"<p style=\"font-family:'{fonts.BODY}'; font-size:{size_body()}px; color:{UI_BG}; "
                f"{LINE_SPACING_CSS} margin-bottom:8px;\">{text}</p>")

    def palette_table():
        rows = []
        for keys in (range(0, 5), range(5, 10)):
            cells = "".join(
                f"<td style=\"padding:4px 14px 4px 0;\"><span style=\"background:{PALETTE[i]};\">"
                f"&nbsp;&nbsp;&nbsp;&nbsp;</span>&nbsp;{_hl(PALETTE_KEYS[i])} "
                f"{PALETTE_NAMES[i]}</td>" for i in keys)
            rows.append(f"<tr>{cells}</tr>")
        return (f"<table style=\"font-family:'{fonts.BODY}'; font-size:{size_body()}px; "
                f"color:{UI_BG}; margin-bottom:8px;\">{''.join(rows)}</table>")

    runs = "<br>".join(
        f"{_hl(d)}: {c['num_graphs']} graphs - "
        + ", ".join(GRAPH_DISPLAY_NAMES[t] for t in c['graph_types'])
        + f" ({c['graphs_per_type']} of each)"
        for d, c in DIFFICULTY_CONFIG.items())
    titles = " | ".join(f"{d}: {c['title']}" for d, c in DIFFICULTY_CONFIG.items())
    return "".join((
        heading("GOAL"),
        para("Color every vertex so that no edge joins two vertices of the same color. Use as few "
             f"colors as you can - the fewest possible is the graph's {_hl('chromatic number')}, "
             "shown as the target in the corner of the board."),
        heading("CONTROLS"),
        para(f"{_hl('Left-click')} a vertex to paint it with the active color. "
             f"{_hl('Right-click')} a vertex to erase it.<br>"
             f"{_hl('H')} buys a hint, {_hl('R')} resets the level, {_hl('ESC')} opens the pause "
             f"menu (the clock keeps running) and {_hl('Shift+S')} forfeits and shows the solution."
             f"<br>{_hl('Mouse wheel')} zooms and {_hl('Middle-drag')} pans."),
        para(f"Conflicting edges turn <span style=\"color:{UI_DANGER_TEXT}\">red</span>. The level "
             "ends the moment every vertex is colored with no conflicts."),
        heading("PALETTE KEYS"),
        para("The palette is two rows of five colors. Click a color, or press its key: "
             f"{_hl('keys 1 to 5')} pick the top row from left to right, and "
             f"{_hl('keys 6, 7, 8, 9 and 0')} pick the bottom row from left to right."),
        palette_table(),
        heading("STANDARD MODE"),
        para(runs),
        para("Before each graph you choose its size n; bigger graphs earn more vertex points. "
             f"Every later level of a graph type needs a {_hl('bigger n')} than the one before. "
             "Once you play a type at its maximum n, it stays locked there."),
        para(f"{_hl('Level score')} = base + time bonus + n x vertex multiplier + optimality bonus "
             "(+500 when you use the minimum number of colors, +200 for one color more)."),
        para(f"{_hl('Resetting')} a level costs 30% of your provisional score. Hit the maximum "
             f"time bonus on every graph of a difficulty and your score is multiplied by "
             f"{_hl('5')}. Closing the game mid-difficulty is not saved - you restart from graph 1."),
        heading("HINTS"),
        para(f"Spend provisional points to reveal a vertex and a safe color for it (EASY "
             f"{HINT_COSTS['EASY']}, MEDIUM {HINT_COSTS['MEDIUM']}, HARD {HINT_COSTS['HARD']} "
             f"points). At most {MAX_HINTS_PER_LEVEL} per level, one every 10 seconds, never "
             f"refunded."),
        heading("FREE MODE"),
        para("Practice any of the 11 graph types at any size. No scoring; hints are free."),
        heading("TITLES"),
        para(titles),
        heading("CREDITS"),
        para("Music: \"Soundtrack\" by Monplaisir, \"Night Shade\" by AdhesiveWombat, "
             "\"Pixelland\" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: "
             "By Attribution 4.0, and \"Alive\" by Tamlin (NCS Release).<br>"
             "Fonts: Press Start 2P (CodeMan38, SIL Open Font License) and Mojangles (Mojang)."),
    ))


class HowToPlayDialog(Overlay):
    def __init__(self, parent=None):
        super().__init__(parent, width_fraction=0.62, min_width=720, max_width=940,
                         max_height_fraction=0.9)
        self.layout_.addWidget(make_label("GUIDE", role="title"))
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.text.setText(guide_html())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.text)
        self.layout_.addWidget(scroll, 1)
        self.layout_.addWidget(make_divider(dark=True))
        self.layout_.addWidget(make_button("CLOSE", self.accept, variant="dark", small=True, icon="close"))

    def _fit_to_host(self):
        super()._fit_to_host()
        self.panel.setFixedHeight(self.panel.maximumHeight())


class LeaderboardDialog(Overlay):
    COLUMNS = ["#", "NAME", "SCORE", "GRAPHS", "DATE"]
    ROW_HEIGHT = 34

    def __init__(self, leaderboard: LeaderboardSystem, parent=None, difficulty: str = None):
        super().__init__(parent, width_fraction=0.56, min_width=680, max_width=860)
        layout = self.layout_
        layout.addWidget(make_label(f"LEADERBOARD - TOP {LEADERBOARD_TOP_N}", role="title"))

        tabs = QHBoxLayout()
        tabs.setSpacing(GAP)
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
        self.stack.setFixedHeight(self.ROW_HEIGHT * (LEADERBOARD_TOP_N + 1) + 8)
        layout.addWidget(self.stack)
        start = DIFFICULTY_ORDER.index(difficulty) if difficulty in DIFFICULTY_ORDER else 0
        self.tab_group.button(start).setChecked(True)
        self.stack.setCurrentIndex(start)

        layout.addWidget(make_divider(dark=True))
        layout.addWidget(make_button("CLOSE", self.accept, variant="dark", small=True, icon="close"))

    def _make_table(self, leaderboard: LeaderboardSystem, difficulty: str) -> QTableWidget:
        entries = leaderboard.get_top_by_difficulty(difficulty)
        table = QTableWidget(max(1, len(entries)), len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        if not entries:
            table.setSpan(0, 0, 1, len(self.COLUMNS))
            table.setItem(0, 0, self._cell("NO SCORES YET - FINISH A RUN TO GET ON THE BOARD",
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


class AchievementsDialog(Overlay):
    def __init__(self, achievements: AchievementSystem, parent=None):
        super().__init__(parent, width_fraction=0.8, min_width=960, max_width=1120)
        layout = self.layout_
        earned = achievements.badges_earned
        layout.addWidget(make_label(f"ACHIEVEMENTS  {len(earned)}/{len(BADGE_INFO)}", role="title"))
        layout.addSpacing(GAP_TIGHT)

        grid = QGridLayout()
        grid.setHorizontalSpacing(GAP + 6)
        grid.setVerticalSpacing(GAP_TIGHT)
        self.badge_labels = {}
        for row, (badge, (name, how)) in enumerate(BADGE_INFO.items()):
            got = badge in earned
            mark = QLabel()
            mark.setPixmap(icon_pixmap("star" if got else "star_outline",
                                       UI_LIME if got else UI_INNER, 2))
            title = make_label(name, align=LEFT)
            desc = make_label(how, align=LEFT)
            for label, color in ((title, UI_LIME if got else UI_INNER),
                                 (desc, UI_BG if got else UI_INNER)):
                set_text_color(label, color)
            grid.addWidget(mark, row, 0)
            grid.addWidget(title, row, 1)
            grid.addWidget(desc, row, 2)
            self.badge_labels[badge] = title
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        layout.addWidget(make_divider(dark=True))
        streaks = "  |  ".join(f"{d}: {achievements.get_streak(d)}" for d in DIFFICULTY_ORDER)
        layout.addWidget(make_label(f"CLEAN-RUN STREAKS - {streaks}"))
        layout.addWidget(make_label(f"GRAPHS SOLVED: {achievements.graphs_solved}"
                                    f" / {COLORBLIND_SOLVES} FOR COLORBLIND", role="caption"))
        layout.addWidget(make_button("CLOSE", self.accept, variant="dark", small=True, icon="close"))


class VolumeDialog(Overlay):
    def __init__(self, settings, music=None, parent=None, on_change=None):
        super().__init__(parent, width_fraction=0.4, min_width=520, max_width=620)
        self.settings = settings
        self.music = music
        self.on_change = on_change
        layout = self.layout_
        layout.addWidget(make_label("VOLUME", role="title"))
        now = track_name(music.current) if music is not None and music.current else "-"
        self.track_label = make_label(f"NOW PLAYING: {now}", role="caption", wrap=True)
        layout.addWidget(self.track_label)
        layout.addSpacing(GAP_TIGHT)

        row = QHBoxLayout()
        row.setSpacing(GAP)
        row.addWidget(make_label("MUSIC", align=LEFT))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setSingleStep(5)
        self.slider.setPageStep(10)
        self.slider.setValue(settings.volume)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.valueChanged.connect(self.set_volume)
        row.addWidget(self.slider, 1)
        self.value_label = make_label(align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setFixedWidth(60)
        row.addWidget(self.value_label)
        layout.addLayout(row)

        self.mute_btn = make_button("", self.toggle_mute, small=True)
        layout.addWidget(self.mute_btn)
        layout.addWidget(make_divider(dark=True))
        layout.addWidget(make_button("CLOSE", self.accept, variant="dark", small=True, icon="close"))
        self._refresh()

    def set_volume(self, value: int):
        self.settings.volume = value
        if value and self.settings.muted:
            self.settings.muted = False
        self._apply()

    def toggle_mute(self):
        self.settings.muted = not self.settings.muted
        self._apply()

    def _apply(self):
        if self.music is not None:
            self.music.set_volume(self.settings.volume)
            self.music.set_muted(self.settings.muted)
        self._refresh()
        if self.on_change:
            self.on_change()

    def _refresh(self):
        muted = self.settings.muted
        self.value_label.setText("OFF" if muted else f"{self.settings.volume}%")
        set_text_color(self.value_label, UI_INNER if muted else UI_LIME)
        self.mute_btn.setText("UNMUTE" if muted else "MUTE")
        self.mute_btn.set_variant("danger" if muted else "light")

    def done(self, result: int):
        self.settings.save()
        super().done(result)
