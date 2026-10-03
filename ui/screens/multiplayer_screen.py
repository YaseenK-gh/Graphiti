from typing import List, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QHBoxLayout, QLineEdit,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from core.constants import (PLAYER_NAME_MAX_LEN, RACE_COLORING, RACE_MODE_NAMES, RACE_PLANAR,
                            RACE_SECONDS, UI_BAD_ON_LIGHT, UI_BORDER, UI_CARD, UI_INK, UI_LIME,
                            UI_LIME_DIM, UI_MUTED_ON_LIGHT)
from core.game_state import GameScreen
from core.validation import validate_player_name
from net.discovery import LobbyBrowser
from net.protocol import CODE_LENGTH, GAME_PORT, clean_code
from ui.fonts import body_font, pixel_font
from ui.overlay import Overlay
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.styles import GAP, GAP_SECTION, GAP_TIGHT, SIZE_BODY, SIZE_SUBTITLE
from ui.widgets.pixel import PixelCard, draw_block

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def mode_text(mode: str, minutes: int = 0) -> str:
    minutes = minutes or RACE_SECONDS.get(mode, 0) // 60
    return f"{RACE_MODE_NAMES.get(mode, mode.upper())} | {minutes} MIN"


class LobbyRow(QAbstractButton):
    SHADOW = 3
    BORDER = 3

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info
        self.setCheckable(True)
        self.setText(info["name"])
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(260, 74)

    def paintEvent(self, event):
        p = QPainter(self)
        dark = self.isChecked() or self.isDown() or self.underMouse()
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        draw_block(p, body, UI_INK if dark else UI_CARD, UI_BORDER, self.BORDER, self.SHADOW)
        inner = body.adjusted(14, 8, -14, -8)
        p.setFont(pixel_font(SIZE_SUBTITLE))
        p.setPen(QColor(UI_LIME if dark else UI_INK))
        p.drawText(QRect(inner.left(), inner.top(), inner.width(), SIZE_SUBTITLE + 8),
                   LEFT, f"{self.info['name']}'S LOBBY")
        p.setFont(body_font(SIZE_BODY))
        p.setPen(QColor(UI_LIME_DIM if dark else UI_BORDER))
        p.drawText(QRect(inner.left(), inner.top() + SIZE_SUBTITLE + 10, inner.width(),
                         SIZE_BODY + 6), LEFT,
                   f"{mode_text(self.info['mode'], self.info.get('minutes', 0))} | "
                   f"{self.info['players']}/{self.info['max']}")


class AddressOverlay(Overlay):
    def __init__(self, parent=None):
        super().__init__(parent, width_fraction=0.44, min_width=560, max_width=680)
        self.address = ""
        self.layout_.addWidget(make_label("JOIN BY ADDRESS", role="title"))
        self.layout_.addWidget(make_label(
            "Type the address shown on the host's lobby screen, for example 192.168.0.12",
            role="body", wrap=True))
        self.input = QLineEdit()
        self.input.setPlaceholderText("HOST ADDRESS")
        self.input.setMaxLength(40)
        self.input.returnPressed.connect(self.confirm)
        self.layout_.addWidget(self.input)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addWidget(make_button("CANCEL", self.reject, variant="dark"))
        buttons.addWidget(make_button("USE ADDRESS", self.confirm))
        self.layout_.addLayout(buttons)

    def _first_focus(self):
        return self.input

    def confirm(self):
        self.address = self.input.text().strip()
        self.accept()


def parse_address(text: str):
    text = (text or "").strip()
    if not text:
        return None
    host, _, port = text.partition(":")
    host = host.strip()
    if not host or " " in host:
        return None
    if not port:
        return host, GAME_PORT
    if not port.isdigit() or not 0 < int(port) < 65536:
        return None
    return host, int(port)


class MultiplayerScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.browser = LobbyBrowser(self)
        self.browser.changed.connect(self.refresh_lobbies)
        self.rows: List[LobbyRow] = []
        self.manual_target = None
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(), 0.78, 980, 1120)
        layout = panel_layout(panel)

        layout.addWidget(make_label("MULTIPLAYER", role="title"))
        layout.addWidget(make_label("PLAY WITH EVERYONE ON THE SAME NETWORK", role="caption"))

        name_row = QHBoxLayout()
        name_row.setSpacing(GAP)
        name_row.addWidget(make_label("YOUR NAME", role="heading", align=LEFT))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("YOUR NAME")
        self.name_input.setMaxLength(PLAYER_NAME_MAX_LEN)
        name_row.addWidget(self.name_input, 1)
        layout.addLayout(name_row)
        layout.addWidget(make_divider())

        columns = QHBoxLayout()
        columns.setSpacing(GAP_SECTION)
        columns.addLayout(self.build_create_column(), 1)
        columns.addLayout(self.build_join_column(), 1)
        layout.addLayout(columns)

        self.notice_label = make_label(role="error", wrap=True)
        layout.addWidget(self.notice_label)
        layout.addWidget(make_divider())
        layout.addWidget(make_button("BACK TO MENU", self.on_back_clicked, small=True, icon="back"))
        outer.addWidget(panel)

    def build_create_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(GAP)
        column.addWidget(make_label("CREATE A LOBBY", role="subtitle", align=LEFT))
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_cards = {}
        for mode, lines in ((RACE_COLORING, ["MOST GRAPHS COLORED WINS", "YOU SET THE LENGTH"]),
                            (RACE_PLANAR, ["MOST GRAPHS UNTANGLED WINS", "YOU SET THE LENGTH"])):
            card = PixelCard(RACE_MODE_NAMES[mode], lines)
            card.setCheckable(True)
            self.mode_group.addButton(card)
            self.mode_cards[mode] = card
            column.addWidget(card)
        self.mode_cards[RACE_COLORING].setChecked(True)
        self.create_btn = make_button("CREATE LOBBY", self.on_create_clicked, icon="play")
        column.addWidget(self.create_btn)
        column.addStretch()
        return column

    def build_join_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(GAP)
        column.addWidget(make_label("JOIN A LOBBY", role="subtitle", align=LEFT))
        self.list_holder = QWidget()
        self.list_layout = QVBoxLayout(self.list_holder)
        self.list_layout.setContentsMargins(0, 0, GAP_TIGHT, 0)
        self.list_layout.setSpacing(GAP_TIGHT)
        self.empty_label = make_label("NO LOBBIES FOUND ON THIS NETWORK YET", role="muted",
                                      wrap=True)
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.list_holder)
        self.scroll.setFixedHeight(170)
        column.addWidget(self.scroll)
        self.row_group = QButtonGroup(self)
        self.row_group.setExclusive(True)

        self.target_label = make_label(role="caption", align=LEFT, wrap=True)
        column.addWidget(self.target_label)
        join_row = QHBoxLayout()
        join_row.setSpacing(GAP)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("CODE")
        self.code_input.setMaxLength(CODE_LENGTH)
        self.code_input.returnPressed.connect(self.on_join_clicked)
        join_row.addWidget(self.code_input, 2)
        self.join_btn = make_button("JOIN", self.on_join_clicked, small=True, icon="play")
        join_row.addWidget(self.join_btn, 3)
        column.addLayout(join_row)
        self.address_btn = make_button("JOIN BY ADDRESS", self.on_address_clicked, small=True)
        column.addWidget(self.address_btn)
        column.addStretch()
        return column

    def on_show(self):
        self.name_input.setText(self.main_window.settings.player_name)
        self.manual_target = None
        if not self.browser.start():
            self.show_notice("LOBBIES CANNOT BE LISTED HERE - USE JOIN BY ADDRESS", error=True)
        self.refresh_lobbies()
        (self.name_input if not self.name_input.text() else self.create_btn).setFocus()

    def on_hide(self):
        self.browser.stop()

    def show_notice(self, text: str, error: bool = False):
        set_text_color(self.notice_label, UI_BAD_ON_LIGHT if error else UI_MUTED_ON_LIGHT)
        self.notice_label.setText(text)

    def selected_mode(self) -> str:
        return next(mode for mode, card in self.mode_cards.items() if card.isChecked())

    def selected_lobby(self) -> Optional[dict]:
        row = self.row_group.checkedButton()
        return row.info if row is not None else None

    def refresh_lobbies(self):
        chosen = self.selected_lobby()
        chosen_id = chosen["id"] if chosen else None
        for row in self.rows:
            self.row_group.removeButton(row)
            self.list_layout.removeWidget(row)
            row.deleteLater()
        self.rows = []
        lobbies = self.browser.lobbies()
        self.empty_label.setVisible(not lobbies)
        for position, info in enumerate(lobbies):
            row = LobbyRow(info)
            row.clicked.connect(self.on_row_clicked)
            self.row_group.addButton(row)
            self.list_layout.insertWidget(position, row)
            self.rows.append(row)
            if info["id"] == chosen_id:
                row.setChecked(True)
        self.update_target()

    def on_row_clicked(self):
        self.manual_target = None
        self.update_target()
        self.code_input.setFocus()

    def update_target(self):
        lobby = self.selected_lobby()
        if self.manual_target is not None:
            self.target_label.setText(f"JOINING {self.manual_target[0]} - ENTER ITS CODE")
        elif lobby is not None:
            self.target_label.setText(f"JOINING {lobby['name']}'S LOBBY - ENTER ITS CODE")
        else:
            self.target_label.setText("PICK A LOBBY, THEN ENTER ITS CODE")

    def player_name(self) -> Optional[str]:
        name, error = validate_player_name(self.name_input.text())
        if error:
            self.show_notice(error.upper(), error=True)
            self.name_input.setFocus()
            return None
        settings = self.main_window.settings
        if settings.player_name != name:
            settings.player_name = name
            settings.save()
        return name

    def on_create_clicked(self):
        name = self.player_name()
        if name is None:
            return
        self.show_notice("")
        error = self.main_window.multiplayer.create_lobby(name, self.selected_mode())
        if error:
            self.show_notice(error, error=True)

    def on_address_clicked(self):
        overlay = AddressOverlay(self)
        if overlay.exec() != Overlay.Accepted:
            return
        target = parse_address(overlay.address)
        if target is None:
            self.show_notice("THAT ADDRESS DOES NOT LOOK RIGHT", error=True)
            return
        checked = self.row_group.checkedButton()
        if checked is not None:
            self.row_group.setExclusive(False)
            checked.setChecked(False)
            self.row_group.setExclusive(True)
        self.manual_target = target
        self.update_target()
        self.show_notice("")
        self.code_input.setFocus()

    def on_join_clicked(self):
        name = self.player_name()
        if name is None:
            return
        lobby = self.selected_lobby()
        if self.manual_target is not None:
            address, port = self.manual_target
        elif lobby is not None:
            address, port = lobby["address"], lobby["port"]
        else:
            self.show_notice("PICK A LOBBY FROM THE LIST FIRST", error=True)
            return
        code = clean_code(self.code_input.text())
        if len(code) != CODE_LENGTH:
            self.show_notice(f"THE LOBBY CODE HAS {CODE_LENGTH} CHARACTERS", error=True)
            self.code_input.setFocus()
            return
        self.show_notice("CONNECTING...")
        self.main_window.multiplayer.join_lobby(address, port, name, code)

    def on_back_clicked(self):
        self.main_window.multiplayer.leave()
        self.main_window.show_screen(GameScreen.MENU)
