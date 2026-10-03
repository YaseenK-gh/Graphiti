import random
import secrets
import uuid
from typing import List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from core.constants import (PLANAR_SEARCH_SECONDS, PLANAR_SEARCH_SLICE_SECONDS,
                            RACE_COUNTDOWN_SECONDS, RACE_MAX_MINUTES, RACE_MAX_PLAYERS,
                            RACE_MIN_MINUTES, RACE_MIN_PLAYERS, RACE_PLANAR, RACE_SECONDS)
from core.race import Race
from core.validation import validate_player_name
from net.discovery import LobbyAnnouncer
from net.protocol import (COUNTDOWN, GAME_PORT, LOBBY, PLAYING, VERSION, LineReader, clean_code,
                          encode, make_code)

TICK_MS = 250
STANDINGS_EVERY = 4


class Peer:
    def __init__(self, socket: QTcpSocket):
        self.socket = socket
        self.reader = LineReader()
        self.id: Optional[int] = None
        self.name = ""
        self.is_host = False

    def send(self, message: dict):
        if self.socket.state() == QTcpSocket.SocketState.ConnectedState:
            self.socket.write(encode(message))


class LobbyHost(QObject):
    changed = Signal()

    def __init__(self, host_name: str, mode: str, parent=None, rng=None, port: int = GAME_PORT,
                 announce: bool = True, countdown_seconds: float = RACE_COUNTDOWN_SECONDS,
                 duration: Optional[float] = None,
                 search_seconds: float = PLANAR_SEARCH_SECONDS):
        super().__init__(parent)
        self.host_name = host_name
        self.mode = mode
        self.rng = rng or random.Random()
        self.wanted_port = port
        self.countdown_seconds = countdown_seconds
        self.duration = duration
        self.minutes = RACE_SECONDS[mode] // 60
        self.search_seconds = search_seconds
        self.code = make_code(self.rng)
        self.host_key = secrets.token_hex(8)
        self.lobby_id = uuid.uuid4().hex
        self.state = LOBBY
        self.race: Optional[Race] = None
        self.peers: List[Peer] = []
        self._next_id = 0
        self._ticks = 0
        self._closed = False

        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._accept)
        self.ticker = QTimer(self)
        self.ticker.setInterval(TICK_MS)
        self.ticker.timeout.connect(self._tick)
        self.starter = QTimer(self)
        self.starter.setSingleShot(True)
        self.starter.timeout.connect(self._begin)
        self.announcer = LobbyAnnouncer(self.describe, self) if announce else None

    def listen(self) -> bool:
        any_address = QHostAddress(QHostAddress.SpecialAddress.AnyIPv4)
        if not self.server.listen(any_address, self.wanted_port) and not self.server.listen(any_address, 0):
            return False
        if self.announcer is not None:
            self.announcer.start()
        return True

    @property
    def port(self) -> int:
        return self.server.serverPort()

    def players(self) -> List[Peer]:
        return sorted((peer for peer in self.peers if peer.id is not None),
                      key=lambda peer: peer.id)

    def describe(self) -> dict:
        count = len(self.players())
        return {"id": self.lobby_id, "name": self.host_name, "mode": self.mode, "players": count,
                "max": RACE_MAX_PLAYERS, "port": self.port, "minutes": self.minutes,
                "open": self.state == LOBBY and count < RACE_MAX_PLAYERS and not self._closed}

    def _lobby_message(self) -> dict:
        return {"t": "lobby", "state": self.state, "mode": self.mode, "minutes": self.minutes,
                "min": RACE_MIN_PLAYERS, "max": RACE_MAX_PLAYERS,
                "players": [{"id": p.id, "name": p.name, "host": p.is_host}
                            for p in self.players()]}

    def _broadcast(self, message: dict):
        for peer in self.players():
            peer.send(message)

    def _broadcast_lobby(self):
        self._broadcast(self._lobby_message())
        if self.announcer is not None:
            self.announcer.announce()
        self.changed.emit()

    def _broadcast_standings(self):
        if self.race is not None:
            self._broadcast({"t": "standings", "rows": self.race.standings(),
                             "remaining": self.race.remaining()})

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            peer = Peer(socket)
            self.peers.append(peer)
            socket.readyRead.connect(lambda p=peer: self._read(p))
            socket.disconnected.connect(lambda p=peer: self._dropped(p))

    def _read(self, peer: Peer):
        for message in peer.reader.feed(bytes(peer.socket.readAll())):
            kind = message.get("t")
            if peer.id is None:
                if kind == "join":
                    self._join(peer, message)
                continue
            if kind == "start":
                self._start(peer)
            elif kind == "length":
                self._length(peer, message)
            elif kind == "submit":
                self._submit(peer, message)
            elif kind == "skip":
                self._skip(peer, message)
            elif kind == "leave":
                self._dropped(peer)

    def _reject(self, peer: Peer, reason: str):
        peer.send({"t": "reject", "reason": reason})
        peer.socket.flush()
        peer.socket.disconnectFromHost()

    def _unique_name(self, name: str) -> str:
        taken = {p.name for p in self.players()}
        if name not in taken:
            return name
        number = 2
        while f"{name} {number}" in taken:
            number += 1
        return f"{name} {number}"

    def _join(self, peer: Peer, message: dict):
        is_host = message.get("host_key") == self.host_key
        if message.get("version") != VERSION:
            return self._reject(peer, "THIS LOBBY RUNS A DIFFERENT GAME VERSION")
        if self.state != LOBBY:
            return self._reject(peer, "THAT MATCH HAS ALREADY STARTED")
        if len(self.players()) >= RACE_MAX_PLAYERS:
            return self._reject(peer, "THAT LOBBY IS FULL")
        if not is_host and clean_code(str(message.get("code", ""))) != self.code:
            return self._reject(peer, "WRONG LOBBY CODE")
        name, error = validate_player_name(str(message.get("name", "")))
        if error:
            return self._reject(peer, error.upper())
        peer.id, self._next_id = self._next_id, self._next_id + 1
        peer.name = self._unique_name(name)
        peer.is_host = is_host
        peer.send({"t": "welcome", "id": peer.id, "name": peer.name, "mode": self.mode,
                   "host": is_host, "code": self.code if is_host else None})
        self._broadcast_lobby()

    def _length(self, peer: Peer, message: dict):
        if not peer.is_host or self.state != LOBBY:
            return
        minutes = message.get("minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool):
            return
        self.minutes = max(RACE_MIN_MINUTES, min(RACE_MAX_MINUTES, minutes))
        self._broadcast_lobby()

    def _start(self, peer: Peer):
        if not peer.is_host or self.state != LOBBY:
            return
        if len(self.players()) < RACE_MIN_PLAYERS:
            peer.send({"t": "error", "reason": f"YOU NEED AT LEAST {RACE_MIN_PLAYERS} PLAYERS"})
            return
        self.state = COUNTDOWN
        self._broadcast_lobby()
        self._broadcast({"t": "countdown", "seconds": self.countdown_seconds})
        self.starter.start(int(self.countdown_seconds * 1000))

    def _begin(self):
        if self.state != COUNTDOWN:
            return
        self.race = Race(self.mode, {p.id: p.name for p in self.players()}, rng=self.rng,
                         duration=self.duration if self.duration is not None
                         else self.minutes * 60, search_seconds=self.search_seconds)
        self.race.start()
        self.state = PLAYING
        self._ticks = 0
        self._broadcast({"t": "begin", "mode": self.mode, "duration": self.race.duration,
                         "remaining": self.race.remaining()})
        first = {"t": "puzzle", "data": self.race.puzzle(0)}
        self._broadcast(first)
        self._broadcast_standings()
        if self.announcer is not None:
            self.announcer.announce()
        self.ticker.start()
        self.changed.emit()

    def _tick(self):
        if self.race is None or self.state != PLAYING:
            return
        if self.race.time_up():
            self._end("time")
            return
        if self.mode == RACE_PLANAR:
            self.race.improve(PLANAR_SEARCH_SLICE_SECONDS)
        self._ticks += 1
        if self._ticks % STANDINGS_EVERY == 0:
            self._broadcast_standings()

    def _submit(self, peer: Peer, message: dict):
        if self.race is None or self.state != PLAYING:
            return
        index = message.get("index")
        ok, reason = self.race.submit(peer.id, index, message.get("data"))
        peer.send({"t": "result", "action": "submit", "ok": ok, "reason": reason, "index": index})
        if ok:
            peer.send({"t": "puzzle", "data": self.race.puzzle(self.race.racers[peer.id].index)})
            self._broadcast_standings()

    def _skip(self, peer: Peer, message: dict):
        if self.race is None or self.state != PLAYING:
            return
        index = message.get("index")
        ok, reason = self.race.skip(peer.id, index)
        racer = self.race.racers[peer.id]
        peer.send({"t": "result", "action": "skip", "ok": ok, "reason": reason, "index": index,
                   "dq": racer.disqualified})
        if ok:
            if not racer.disqualified:
                peer.send({"t": "puzzle", "data": self.race.puzzle(racer.index)})
            self._broadcast_standings()

    def _end(self, reason: str):
        if self.race is None or self.state != PLAYING:
            return
        self.ticker.stop()
        self.race.finish()
        self._broadcast({"t": "end", "reason": reason, "mode": self.mode,
                         "rows": self.race.standings(),
                         "planar": self.race.planar_summary() if self.mode == RACE_PLANAR else []})
        self.state = LOBBY
        self._broadcast_lobby()

    def _dropped(self, peer: Peer):
        if peer not in self.peers:
            return
        self.peers.remove(peer)
        peer.socket.disconnectFromHost()
        peer.socket.deleteLater()
        if peer.id is None or self._closed:
            return
        if peer.is_host:
            self.close()
            return
        if self.state == PLAYING and self.race is not None:
            self.race.leave(peer.id)
            self._broadcast_standings()
        elif self.state == COUNTDOWN and len(self.players()) < RACE_MIN_PLAYERS:
            self.starter.stop()
            self.state = LOBBY
        self._broadcast_lobby()

    def close(self):
        if self._closed:
            return
        if self.state == PLAYING:
            self._end("host_left")
        self._closed = True
        self.ticker.stop()
        self.starter.stop()
        if self.announcer is not None:
            self.announcer.announce()
            self.announcer.stop()
        self._broadcast({"t": "closed"})
        for peer in list(self.peers):
            peer.socket.flush()
            peer.socket.disconnectFromHost()
        self.peers.clear()
        self.server.close()
        self.changed.emit()
