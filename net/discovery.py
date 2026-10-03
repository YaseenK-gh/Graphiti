import json
import time
from typing import Callable, Dict, List

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface, QUdpSocket

from net.protocol import APP, DISCOVERY_PORT, VERSION

ANNOUNCE_MS = 1000
EXPIRY_SECONDS = 3.5


def broadcast_addresses() -> List[QHostAddress]:
    found = {"255.255.255.255", "127.0.0.1"}
    for interface in QNetworkInterface.allInterfaces():
        flags = interface.flags()
        if not (flags & QNetworkInterface.InterfaceFlag.IsUp
                and flags & QNetworkInterface.InterfaceFlag.IsRunning):
            continue
        if flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
            continue
        for entry in interface.addressEntries():
            if entry.ip().protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                continue
            if not entry.broadcast().isNull():
                found.add(entry.broadcast().toString())
    return [QHostAddress(text) for text in sorted(found)]


def local_addresses() -> List[str]:
    found = []
    for address in QNetworkInterface.allAddresses():
        if (address.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol
                and not address.isLoopback()):
            found.append(address.toString())
    return found


class LobbyAnnouncer(QObject):
    def __init__(self, describe: Callable[[], dict], parent=None, port: int = DISCOVERY_PORT):
        super().__init__(parent)
        self.describe = describe
        self.port = port
        self.socket = QUdpSocket(self)
        self.timer = QTimer(self)
        self.timer.setInterval(ANNOUNCE_MS)
        self.timer.timeout.connect(self.announce)

    def start(self):
        self.announce()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def announce(self):
        payload = json.dumps(dict(self.describe(), app=APP, v=VERSION)).encode("utf-8")
        for address in broadcast_addresses():
            self.socket.writeDatagram(payload, address, self.port)


class LobbyBrowser(QObject):
    changed = Signal()

    def __init__(self, parent=None, port: int = DISCOVERY_PORT):
        super().__init__(parent)
        self.port = port
        self.socket = QUdpSocket(self)
        self.socket.readyRead.connect(self._read)
        self.found: Dict[str, dict] = {}
        self.listening = False
        self.timer = QTimer(self)
        self.timer.setInterval(ANNOUNCE_MS)
        self.timer.timeout.connect(self._prune)

    def start(self) -> bool:
        if not self.listening:
            self.listening = self.socket.bind(
                QHostAddress(QHostAddress.SpecialAddress.AnyIPv4), self.port,
                QUdpSocket.BindFlag.ShareAddress | QUdpSocket.BindFlag.ReuseAddressHint)
        self.timer.start()
        return self.listening

    def stop(self):
        self.timer.stop()
        if self.listening:
            self.socket.close()
            self.listening = False
        if self.found:
            self.found.clear()
            self.changed.emit()

    def lobbies(self) -> List[dict]:
        return sorted((info for info in self.found.values() if info.get("open")),
                      key=lambda info: (info["name"], info["id"]))

    def _read(self):
        updated = False
        while self.socket.hasPendingDatagrams():
            datagram = self.socket.receiveDatagram()
            try:
                info = json.loads(bytes(datagram.data()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(info, dict) or info.get("app") != APP or info.get("v") != VERSION:
                continue
            try:
                entry = {"id": str(info["id"]), "name": str(info["name"])[:24],
                         "mode": str(info["mode"]), "players": int(info["players"]),
                         "max": int(info["max"]), "port": int(info["port"]),
                         "open": bool(info["open"]), "minutes": int(info.get("minutes", 0))}
            except (KeyError, TypeError, ValueError):
                continue
            address = datagram.senderAddress().toString()
            entry["address"] = address[7:] if address.startswith("::ffff:") else address
            entry["seen"] = time.monotonic()
            previous = self.found.get(entry["id"])
            self.found[entry["id"]] = entry
            if previous is None or any(previous[k] != entry[k]
                                       for k in ("name", "mode", "players", "open", "port",
                                                 "minutes")):
                updated = True
        if updated:
            self.changed.emit()

    def _prune(self):
        cutoff = time.monotonic() - EXPIRY_SECONDS
        stale = [key for key, info in self.found.items() if info["seen"] < cutoff]
        for key in stale:
            del self.found[key]
        if stale:
            self.changed.emit()
