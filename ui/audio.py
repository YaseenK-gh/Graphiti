import glob
import logging
import os
import random
from typing import List, Optional

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudio, QAudioOutput, QMediaPlayer

from core.constants import PROJECT_ROOT

logger = logging.getLogger(__name__)

MUSIC_DIR = os.path.join(PROJECT_ROOT, "assets", "music")

TRACK_NAMES = {
    "monplaisir-soundtrack": "MONPLAISIR - SOUNDTRACK",
    "adhesivewombat-night-shade": "ADHESIVEWOMBAT - NIGHT SHADE",
    "kevin-macleod-pixelland": "KEVIN MACLEOD - PIXELLAND",
    "tamlin-alive": "TAMLIN - ALIVE",
}


def track_name(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return TRACK_NAMES.get(stem, stem.replace("-", " ").upper())


def shuffled_order(tracks: List[str], rng=random, avoid_first: Optional[str] = None) -> List[str]:
    order = list(tracks)
    rng.shuffle(order)
    if len(order) > 1 and order[0] == avoid_first:
        order[0], order[-1] = order[-1], order[0]
    return order


class MusicPlayer(QObject):
    def __init__(self, folder: str = MUSIC_DIR, rng=random, parent=None):
        super().__init__(parent)
        self.tracks = sorted(glob.glob(os.path.join(folder, "*.mp3")))
        self.rng = rng
        self.queue: List[str] = []
        self.current: Optional[str] = None
        self._failures = 0
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)

    def start(self):
        if self.tracks:
            self.play_next()
        else:
            logger.info("No music found in %s", MUSIC_DIR)

    def play_next(self):
        if not self.queue:
            self.queue = shuffled_order(self.tracks, self.rng, avoid_first=self.current)
        self.current = self.queue.pop(0)
        self.player.setSource(QUrl.fromLocalFile(self.current))
        self.player.play()

    def set_volume(self, volume: int):
        linear = QAudio.convertVolume(max(0, min(100, volume)) / 100,
                                      QAudio.VolumeScale.LogarithmicVolumeScale,
                                      QAudio.VolumeScale.LinearVolumeScale)
        self.output.setVolume(linear)

    def set_muted(self, muted: bool):
        self.output.setMuted(muted)

    def stop(self):
        self.player.stop()

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._failures = 0
            self.play_next()

    def _on_error(self, error, message):
        logger.warning("Could not play %s: %s", self.current, message)
        self._failures += 1
        if self._failures < len(self.tracks):
            self.play_next()
