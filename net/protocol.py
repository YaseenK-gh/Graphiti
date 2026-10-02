import json
import random
from typing import List

APP = "graphiti"
VERSION = 1
DISCOVERY_PORT = 47800
GAME_PORT = 47801
MAX_LINE = 1 << 20
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4

LOBBY, COUNTDOWN, PLAYING = "lobby", "countdown", "playing"


def make_code(rng=random) -> str:
    return "".join(rng.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def clean_code(text: str) -> str:
    return "".join((text or "").split()).upper()


def encode(message: dict) -> bytes:
    return json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"


class LineReader:
    def __init__(self):
        self.buffer = b""

    def feed(self, data: bytes) -> List[dict]:
        self.buffer += data
        messages = []
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                message = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(message, dict):
                messages.append(message)
        if len(self.buffer) > MAX_LINE:
            self.buffer = b""
        return messages
