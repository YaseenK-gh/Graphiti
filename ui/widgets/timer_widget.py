from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel

from core.constants import UI_LIME
from ui.fonts import pixel_font
from ui.styles import SIZE_TIMER


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class TimerWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__("00:00", parent)
        self._color = UI_LIME
        self.setMinimumHeight(SIZE_TIMER + 16)

    def sizeHint(self) -> QSize:
        return QSize(SIZE_TIMER * 5 + 10, SIZE_TIMER + 16)

    def set_elapsed(self, seconds: float):
        text = format_time(seconds)
        if text != self.text():
            self.setText(text)

    def set_color(self, color: str):
        if color != self._color:
            self._color = color
            self.update()

    def color(self) -> str:
        return self._color

    def paintEvent(self, event):
        p = QPainter(self)
        p.setFont(pixel_font(SIZE_TIMER))
        p.setPen(QColor(self._color))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
