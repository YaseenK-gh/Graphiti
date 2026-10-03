import time
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QTcpSocket

from net.protocol import LOBBY, PLAYING, VERSION, LineReader, encode


class LobbyClient(QObject):
    joined = Signal()
    rejected = Signal(str)
    lobby_changed = Signal()
    countdown_started = Signal(float)
    began = Signal()
    puzzle_received = Signal(dict)
    result_received = Signal(dict)
    standings_changed = Signal()
    ended = Signal()
    closed = Signal(str)
    error_received = Signal(str)

    def __init__(self, parent=None, clock: Callable[[], float] = time.monotonic):
        super().__init__(parent)
        self.clock = clock
        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self._on_connected)
        self.socket.readyRead.connect(self._read)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.errorOccurred.connect(self._socket_error)
        self.reader = LineReader()
        self.handlers = {"welcome": self._on_welcome, "reject": self._on_reject,
                         "error": self._on_error, "lobby": self._on_lobby,
                         "countdown": self._on_countdown, "begin": self._on_begin,
                         "puzzle": self._on_puzzle, "result": self._on_result,
                         "standings": self._on_standings, "end": self._on_end,
                         "closed": self._on_closed}
        self._hello: Optional[dict] = None
        self._finished = False

        self.my_id: Optional[int] = None
        self.name = ""
        self.mode = ""
        self.code: Optional[str] = None
        self.is_host = False
        self.address = ""
        self.port = 0
        self.state = LOBBY
        self.players: List[dict] = []
        self.min_players = 2
        self.minutes = 0
        self.max_players = 20
        self.rows: List[dict] = []
        self.deadline: Optional[float] = None
        self.duration = 0.0
        self.puzzle: Optional[dict] = None
        self.results: Optional[dict] = None
        self.connected = False

    def connect_to(self, address: str, port: int, name: str, code: str = "", host_key: str = ""):
        self.address, self.port = address, port
        self._hello = {"t": "join", "version": VERSION, "name": name, "code": code,
                       "host_key": host_key}
        self.socket.connectToHost(address, port)

    def _on_connected(self):
        self.send(self._hello)

    def send(self, message: dict):
        if self.socket.state() == QTcpSocket.SocketState.ConnectedState:
            self.socket.write(encode(message))

    def start(self):
        self.send({"t": "start"})

    def set_minutes(self, minutes: int):
        self.send({"t": "length", "minutes": int(minutes)})

    def submit(self, index: int, data):
        self.send({"t": "submit", "index": index, "data": data})

    def skip(self, index: int):
        self.send({"t": "skip", "index": index})

    def leave(self):
        self._finished = True
        self.connected = False
        if self.socket.state() == QTcpSocket.SocketState.ConnectedState:
            self.send({"t": "leave"})
            self.socket.flush()
        self.socket.abort()

    def remaining(self) -> float:
        return 0.0 if self.deadline is None else max(0.0, self.deadline - self.clock())

    def my_row(self) -> Optional[dict]:
        return next((row for row in self.rows if row["id"] == self.my_id), None)

    def in_match(self) -> bool:
        return self.state == PLAYING

    def _read(self):
        for message in self.reader.feed(bytes(self.socket.readAll())):
            if self._finished:
                return
            handler = self.handlers.get(message.get("t"))
            if handler is not None:
                handler(message)

    def _on_welcome(self, message: dict):
        self.my_id = message.get("id")
        self.name = message.get("name", "")
        self.mode = message.get("mode", "")
        self.is_host = bool(message.get("host"))
        self.code = message.get("code")
        self.connected = True
        self.joined.emit()

    def _on_reject(self, message: dict):
        self._finished = True
        self.socket.abort()
        self.rejected.emit(str(message.get("reason", "COULD NOT JOIN")))

    def _on_error(self, message: dict):
        self.error_received.emit(str(message.get("reason", "")))

    def _socket_error(self, _error):
        if self._finished or self.connected:
            return
        self._finished = True
        self.rejected.emit("COULD NOT REACH THAT LOBBY")

    def _on_lobby(self, message: dict):
        self.players = list(message.get("players", []))
        self.mode = message.get("mode", self.mode)
        self.minutes = message.get("minutes", self.minutes)
        self.min_players = message.get("min", self.min_players)
        self.max_players = message.get("max", self.max_players)
        state = message.get("state", LOBBY)
        if state != PLAYING:
            self.state = state
        self.lobby_changed.emit()

    def _on_countdown(self, message: dict):
        self.countdown_started.emit(float(message.get("seconds", 0)))

    def _on_begin(self, message: dict):
        self.state = PLAYING
        self.mode = message.get("mode", self.mode)
        self.duration = float(message.get("duration", 0))
        self.deadline = self.clock() + float(message.get("remaining", self.duration))
        self.results = None
        self.puzzle = None
        self.rows = []
        self.began.emit()

    def _on_puzzle(self, message: dict):
        self.puzzle = message.get("data")
        if self.puzzle is not None:
            self.puzzle_received.emit(self.puzzle)

    def _on_result(self, message: dict):
        self.result_received.emit(message)

    def _on_standings(self, message: dict):
        self.rows = list(message.get("rows", []))
        if "remaining" in message and self.state == PLAYING:
            self.deadline = self.clock() + float(message["remaining"])
        self.standings_changed.emit()

    def _on_end(self, message: dict):
        self.rows = list(message.get("rows", []))
        self.results = {"reason": message.get("reason", "time"), "rows": self.rows,
                        "mode": message.get("mode", self.mode),
                        "planar": message.get("planar", [])}
        self.state = LOBBY
        self.deadline = None
        self.ended.emit()

    def _on_closed(self, message: dict):
        self._lost("THE HOST CLOSED THE LOBBY")

    def _on_disconnected(self):
        if not self._finished:
            self._lost("THE CONNECTION TO THE HOST WAS LOST")

    def _lost(self, reason: str):
        if self._finished:
            return
        self._finished = True
        was_connected = self.connected
        self.connected = False
        self.socket.abort()
        if not was_connected:
            self.rejected.emit("COULD NOT REACH THAT LOBBY")
            return
        if self.state == PLAYING:
            self.results = {"reason": "host_left", "rows": self.rows, "mode": self.mode,
                            "planar": []}
            self.state = LOBBY
            self.deadline = None
            self.ended.emit()
        self.closed.emit(reason)
