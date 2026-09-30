"""Large MM:SS LCD timer: faint 88:88 ghost digits, a hard shadow, then the time."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QLabel

from core.constants import UI_DARK_LINE, UI_LIME, UI_TIMER_SHADOW
from ui.fonts import pixel_font
from ui.styles import SIZE_TIMER


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class TimerWidget(QLabel):

    SHADOW = 3

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
        align = Qt.AlignmentFlag.AlignCenter
        rect = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        p.setPen(QColor(UI_DARK_LINE))
        p.drawText(rect, align, "88:88")
        p.setPen(QColor(UI_TIMER_SHADOW))
        p.drawText(rect.translated(self.SHADOW, self.SHADOW), align, self.text())
        p.setPen(QColor(self._color))
        p.drawText(rect, align, self.text())
