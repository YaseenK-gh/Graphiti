from typing import Optional

from PySide6.QtCore import QObject

from core.game_state import GameMode, GameScreen
from net.client import LobbyClient
from net.host import LobbyHost
from net.protocol import GAME_PORT


class MultiplayerController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.host: Optional[LobbyHost] = None
        self.session: Optional[LobbyClient] = None
        self.host_options = {}

    def screen(self, which: GameScreen):
        return self.window.screens[which]

    def current(self) -> GameScreen:
        return self.window.game_state.current_screen

    def create_lobby(self, name: str, mode: str) -> Optional[str]:
        self.leave()
        host = LobbyHost(name, mode, parent=self, **self.host_options)
        if not host.listen():
            host.deleteLater()
            return "COULD NOT OPEN A LOBBY ON THIS COMPUTER"
        self.host = host
        self._connect("127.0.0.1", host.port, name, host_key=host.host_key)
        return None

    def join_lobby(self, address: str, port: int, name: str, code: str):
        self.leave()
        self._connect(address, port or GAME_PORT, name, code=code)

    def _connect(self, address: str, port: int, name: str, code: str = "", host_key: str = ""):
        session = LobbyClient(self)
        session.joined.connect(self.on_joined)
        session.rejected.connect(self.on_rejected)
        session.lobby_changed.connect(self.on_lobby_changed)
        session.countdown_started.connect(self.on_countdown)
        session.began.connect(self.on_began)
        session.puzzle_received.connect(self.on_puzzle)
        session.result_received.connect(self.on_result)
        session.standings_changed.connect(self.on_standings)
        session.ended.connect(self.on_ended)
        session.closed.connect(self.on_closed)
        session.error_received.connect(self.on_error)
        self.session = session
        session.connect_to(address, port, name, code, host_key)

    def leave(self):
        session, host = self.session, self.host
        self.session, self.host = None, None
        if session is not None:
            session.leave()
            session.deleteLater()
        if host is not None:
            host.close()
            host.deleteLater()

    def on_joined(self):
        self.window.game_state.game_mode = GameMode.RACE
        self.window.show_screen(GameScreen.LOBBY)

    def on_rejected(self, reason: str):
        self.leave()
        if self.current() != GameScreen.MULTIPLAYER:
            self.window.show_screen(GameScreen.MULTIPLAYER)
        self.screen(GameScreen.MULTIPLAYER).show_notice(reason, error=True)

    def on_error(self, reason: str):
        if self.current() == GameScreen.LOBBY:
            self.screen(GameScreen.LOBBY).show_status(reason, error=True)

    def on_lobby_changed(self):
        if self.current() == GameScreen.LOBBY:
            self.screen(GameScreen.LOBBY).refresh()
        elif self.current() == GameScreen.RACE_RESULTS:
            self.screen(GameScreen.RACE_RESULTS).refresh_buttons()

    def on_countdown(self, seconds: float):
        if self.current() != GameScreen.LOBBY:
            self.window.show_screen(GameScreen.LOBBY)
        self.screen(GameScreen.LOBBY).start_countdown(seconds)

    def on_began(self):
        self.window.show_screen(GameScreen.RACE)

    def on_puzzle(self, data: dict):
        if self.current() == GameScreen.RACE:
            self.screen(GameScreen.RACE).load_puzzle(data)

    def on_result(self, message: dict):
        if self.current() == GameScreen.RACE:
            self.screen(GameScreen.RACE).on_result(message)

    def on_standings(self):
        if self.current() == GameScreen.RACE:
            self.screen(GameScreen.RACE).update_standings()

    def on_ended(self):
        if self.current() == GameScreen.RACE:
            self.screen(GameScreen.RACE).on_match_ended()
        self.window.show_screen(GameScreen.RACE_RESULTS)

    def on_closed(self, reason: str):
        host = self.host
        self.host = None
        if host is not None:
            host.close()
            host.deleteLater()
        if self.current() == GameScreen.RACE_RESULTS:
            self.screen(GameScreen.RACE_RESULTS).on_session_closed(reason)
            return
        self.leave()
        self.window.show_screen(GameScreen.MULTIPLAYER)
        self.screen(GameScreen.MULTIPLAYER).show_notice(reason, error=True)
