"""10-swatch color palette (keys 1–9, 0), in a 5×2 grid."""

from typing import List, Optional

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QSizePolicy, QWidget

from core.constants import (PALETTE, PALETTE_KEYS, PALETTE_NAMES, UI_BORDER, UI_GOLD, UI_INK,
                            UI_LIME)
from ui.fonts import pixel_font


def text_color_for(fill: str) -> str:
    """White on dark fills, ink on light ones."""
    c = QColor(fill)
    luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return "#FFFFFF" if luminance < 150 else UI_INK


class Swatch(QAbstractButton):
    HEIGHT = 38

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.active = False
        self.suggested = False
        self.setText(PALETTE_KEYS[index])
        self.setToolTip(f"{PALETTE_NAMES[index]} (key {PALETTE_KEYS[index]})")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(52, self.HEIGHT)

    def paintEvent(self, event):
        p = QPainter(self)
        fill = PALETTE[self.index]
        r = self.rect()
        if self.active:
            p.fillRect(r, QColor(UI_INK))
            p.fillRect(r.adjusted(1, 1, -1, -1), QColor(UI_LIME))
            body = r.adjusted(4, 4, -4, -4)
        else:
            body = r.adjusted(2, 2, -2, -2)
            p.fillRect(r, QColor(UI_LIME if self.underMouse() else UI_BORDER))
        p.fillRect(body, QColor(fill))
        if self.suggested and not self.active:
            pen = QPen(QColor(UI_GOLD), 3, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRect(r.adjusted(1, 1, -2, -2))
        p.setPen(QColor(text_color_for(fill)))
        p.setFont(pixel_font(12))
        p.drawText(QRect(body), Qt.AlignmentFlag.AlignCenter, self.text())


class ColorPalette(QWidget):
    color_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = 0
        self.suggested: Optional[int] = None
        self.buttons: List[Swatch] = []
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for i in range(len(PALETTE)):
            swatch = Swatch(i)
            swatch.clicked.connect(lambda _checked=False, idx=i: self._on_click(idx))
            grid.addWidget(swatch, i // 5, i % 5)
            self.buttons.append(swatch)
        self._refresh()

    def _on_click(self, index: int):
        self.set_active(index)
        self.color_selected.emit(index)

    def set_active(self, index: int):
        self.active = index
        self._refresh()

    def set_suggested(self, index: Optional[int]):
        self.suggested = index
        self._refresh()

    def _refresh(self):
        for i, swatch in enumerate(self.buttons):
            swatch.active = i == self.active
            swatch.suggested = i == self.suggested
            swatch.update()
