import math
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from core.constants import UI_BAD_ON_LIGHT, UI_GOOD_ON_LIGHT, UI_MUTED_ON_LIGHT
from core.game_state import GameScreen
from net.discovery import local_addresses
from net.protocol import COUNTDOWN, GAME_PORT
from ui.overlay import confirm
from ui.screens import (BaseScreen, make_button, make_divider, make_label, make_panel,
                        panel_layout, set_text_color)
from ui.screens.multiplayer_screen import mode_text
from ui.styles import GAP, GAP_TIGHT

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class LobbyScreen(BaseScreen):
    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self.countdown_deadline = None
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.init_ui()

    @property
    def session(self):
        return self.main_window.multiplayer.session

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel = self.fit(make_panel(), 0.6, 760, 900)
        layout = panel_layout(panel)

        self.mode_label = make_label(role="caption")
        layout.addWidget(self.mode_label)
        self.title_label = make_label(role="title")
        layout.addWidget(self.title_label)
        self.code_label = make_label(role="badge")
        layout.addWidget(self.code_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.address_label = make_label(role="caption", wrap=True)
        layout.addWidget(self.address_label)
        layout.addWidget(make_divider())

        self.count_label = make_label(role="subtitle", align=LEFT)
        layout.addWidget(self.count_label)
        self.list_holder = QWidget()
        self.list_layout = QVBoxLayout(self.list_holder)
        self.list_layout.setContentsMargins(0, 0, GAP_TIGHT, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.list_holder)
        self.scroll.setFixedHeight(230)
        layout.addWidget(self.scroll)
        self.player_labels = []

        self.status_label = make_label(role="heading", wrap=True)
        layout.addWidget(self.status_label)
        layout.addWidget(make_divider())

        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.leave_btn = make_button("LEAVE LOBBY", self.on_leave_clicked, icon="back")
        self.start_btn = make_button("START MATCH", self.on_start_clicked, icon="play")
        buttons.addWidget(self.leave_btn)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)
        outer.addWidget(panel)

    def on_show(self):
        self.stop_countdown()
        self.refresh()
        (self.start_btn if self.start_btn.isVisible() else self.leave_btn).setFocus()

    def on_hide(self):
        self.stop_countdown()

    def refresh(self):
        session = self.session
        if session is None:
            return
        host = next((p for p in session.players if p.get("host")), None)
        self.mode_label.setText(f"LOBBY | {mode_text(session.mode)}")
        self.title_label.setText(f"{host['name']}'S LOBBY" if host else "LOBBY")
        self.code_label.setVisible(session.is_host)
        self.address_label.setVisible(session.is_host)
        if session.is_host:
            self.code_label.setText(f"LOBBY CODE: {session.code}")
            addresses = local_addresses()
            port = session.port
            shown = ", ".join(a if port == GAME_PORT else f"{a}:{port}" for a in addresses)
            self.address_label.setText(f"TELL PLAYERS THE CODE. ADDRESS FOR JOIN BY ADDRESS: "
                                       f"{shown or 'NOT CONNECTED TO A NETWORK'}")

        for label in self.player_labels:
            self.list_layout.removeWidget(label)
            label.deleteLater()
        self.player_labels = []
        for number, player in enumerate(session.players, 1):
            tags = [tag for tag, on in (("HOST", player.get("host")),
                                        ("YOU", player.get("id") == session.my_id)) if on]
            text = f"{number}. {player['name']}" + (f"  ({', '.join(tags)})" if tags else "")
            label = make_label(text, align=LEFT)
            self.list_layout.insertWidget(number - 1, label)
            self.player_labels.append(label)
        self.count_label.setText(f"PLAYERS {len(session.players)}/{session.max_players}")

        ready = len(session.players) >= session.min_players
        counting = session.state == COUNTDOWN
        self.start_btn.setVisible(session.is_host)
        self.start_btn.setEnabled(ready and not counting)
        if not counting:
            self.stop_countdown()
            if not ready:
                self.show_status(f"WAITING FOR AT LEAST {session.min_players} PLAYERS")
            elif session.is_host:
                self.show_status("READY - START WHEN EVERYONE IS IN", good=True)
            else:
                self.show_status("WAITING FOR THE HOST TO START")

    def show_status(self, text: str, error: bool = False, good: bool = False):
        set_text_color(self.status_label, UI_BAD_ON_LIGHT if error
                       else UI_GOOD_ON_LIGHT if good else UI_MUTED_ON_LIGHT)
        self.status_label.setText(text)

    def start_countdown(self, seconds: float):
        self.countdown_deadline = time.monotonic() + seconds
        self.start_btn.setEnabled(False)
        self.countdown_timer.start()
        self.update_countdown()

    def stop_countdown(self):
        self.countdown_timer.stop()
        self.countdown_deadline = None

    def update_countdown(self):
        if self.countdown_deadline is None:
            return
        left = max(0.0, self.countdown_deadline - time.monotonic())
        self.show_status(f"STARTING IN {max(1, math.ceil(left))}", good=True)

    def on_start_clicked(self):
        if self.session is not None:
            self.session.start()

    def on_leave_clicked(self):
        session = self.session
        if session is not None and session.is_host and len(session.players) > 1:
            if not confirm(self, "Close lobby?",
                           "You are the host. Leaving closes the lobby for everyone.",
                           yes="CLOSE LOBBY", no="STAY", danger=True):
                return
        self.main_window.multiplayer.leave()
        self.main_window.show_screen(GameScreen.MULTIPLAYER)
