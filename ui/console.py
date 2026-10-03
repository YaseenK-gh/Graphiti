import sys
import threading

from PySide6.QtCore import QObject, Signal

from core.commands import USAGE, run_command
from core.game_state import GameScreen


class TerminalCommands(QObject):
    line_received = Signal(str)

    def __init__(self, window, stream=None):
        super().__init__(window)
        self.window = window
        self.stream = stream if stream is not None else sys.stdin
        self.line_received.connect(self.handle)

    def start(self) -> bool:
        if self.stream is None or not self.stream.isatty():
            return False
        print(f"Graphiti commands: type them here while the game runs. {USAGE}", flush=True)
        threading.Thread(target=self._listen, daemon=True).start()
        return True

    def _listen(self):
        for line in self.stream:
            self.line_received.emit(line)

    def handle(self, line: str):
        message = run_command(line, self.window.game_state.wallet)
        if not message:
            return
        print(message, flush=True)
        if self.window.game_state.current_screen == GameScreen.MENU:
            self.window.screens[GameScreen.MENU].update_stats()
