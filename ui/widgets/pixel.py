"""Self-painted pixel widgets: panels, buttons, cards, dividers and the dotted page.

Qt stylesheets can't draw hard offset shadows or double borders, so these
paint the reference design's blocks directly.
"""

from typing import List, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QFrame, QPushButton, QSizePolicy, QWidget

from core.constants import (UI_BG, UI_BORDER, UI_BUTTON, UI_CARD, UI_DANGER_BG, UI_DANGER_TEXT,
                            UI_DARK_LINE, UI_DOT, UI_EASY, UI_INK, UI_INNER, UI_LIME, UI_LIME_DIM,
                            UI_PANEL)
from ui.fonts import pixel_font, terminal_font


def draw_block(p: QPainter, rect: QRect, fill: str, border: str = UI_BORDER, border_w: int = 3,
               shadow: int = 0, inner: Optional[str] = None):
    """A filled box with a solid border, an optional hard drop shadow and an inner rule."""
    if shadow:
        p.fillRect(rect.translated(shadow, shadow), QColor(border))
    p.fillRect(rect, QColor(border))
    p.fillRect(rect.adjusted(border_w, border_w, -border_w, -border_w), QColor(fill))
    if inner:
        pen = QPen(QColor(inner), 2)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = border_w + 3
        p.drawRect(rect.adjusted(inset, inset, -inset - 1, -inset - 1))


def dot_tile(bg: str, dot: str, size: int = 16) -> QPixmap:
    """Tile for the dotted LCD background: a dot every 16px, fainter ones between."""
    tile = QPixmap(size, size)
    tile.fill(QColor(bg))
    p = QPainter(tile)
    p.fillRect(0, 0, 2, 2, QColor(dot))
    faint = QColor(dot)
    faint.setAlpha(110)
    q = size // 4
    for x, y in ((q, q), (3 * q, q), (q, 3 * q), (3 * q, 3 * q)):
        p.fillRect(x, y, 1, 1, faint)
    p.end()
    return tile


class PixelBackground(QWidget):
    """The dotted page every screen sits on."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tile = dot_tile(UI_BG, UI_DOT)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawTiledPixmap(self.rect(), self._tile)


class PixelPanel(QFrame):
    """Panel with a 4px border, an inner rule and a hard shadow. tone: 'light' or 'dark'."""

    SHADOW = 4
    BORDER = 4

    def __init__(self, tone: str = "light", parent=None):
        super().__init__(parent)
        self.setProperty("tone", tone)
        self.tone = tone
        self.setContentsMargins(0, 0, self.SHADOW, self.SHADOW)

    def paintEvent(self, event):
        p = QPainter(self)
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        fill = UI_INK if self.tone == "dark" else UI_PANEL
        draw_block(p, body, fill, UI_BORDER, self.BORDER, self.SHADOW, inner=UI_INNER)


class Divider(QFrame):
    def __init__(self, dark: bool = False, parent=None):
        super().__init__(parent)
        self.color = UI_DARK_LINE if dark else UI_BORDER
        self.setFixedHeight(3)

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), QColor(self.color))


# (normal fill, normal text, hover fill, hover text, pressed/checked fill, pressed text)
BUTTON_VARIANTS = {
    "light": (UI_BUTTON, UI_INK, UI_INK, UI_BG, UI_INK, UI_BG),
    "dark": (UI_DARK_LINE, UI_LIME_DIM, UI_LIME, UI_INK, UI_LIME, UI_INK),
    "danger": (UI_DANGER_BG, UI_DANGER_TEXT, UI_DANGER_TEXT, UI_INK, UI_DANGER_TEXT, UI_INK),
    "tab": (UI_DARK_LINE, UI_LIME_DIM, UI_EASY, UI_INK, UI_LIME, UI_INK),
}


class PixelButton(QPushButton):
    """Chunky button: border + hard shadow; inverts on hover and sinks into its shadow when pressed."""

    SHADOW = 3
    BORDER = 3

    def __init__(self, text: str = "", variant: str = "light", small: bool = False, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.pad_x, self.pad_y = (12, 8) if small else (16, 12)
        px = 12 if small else 14
        # setFont gives correct metrics before polish; the widget-level stylesheet keeps the
        # app-wide QWidget rule from overriding it afterwards.
        self.setFont(pixel_font(px))
        self.setStyleSheet(f"font-size: {px}px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_variant(self, variant: str):
        self.variant = variant
        self.update()

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        extra = 2 * self.BORDER + self.SHADOW
        return QSize(fm.horizontalAdvance(self.text()) + 2 * self.pad_x + extra,
                     fm.height() + 2 * self.pad_y + extra)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, event):
        p = QPainter(self)
        fill, fg, hover_fill, hover_fg, down_fill, down_fg = BUTTON_VARIANTS[self.variant]
        enabled = self.isEnabled()
        down = enabled and (self.isDown() or self.isChecked())
        hover = enabled and self.underMouse()
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        if not enabled:
            p.setOpacity(0.45)
        if down:
            body.translate(self.SHADOW, self.SHADOW)
            draw_block(p, body, down_fill, UI_BORDER, self.BORDER)
            fg = down_fg
        elif hover:
            draw_block(p, body, hover_fill, UI_BORDER, self.BORDER, self.SHADOW)
            fg = hover_fg
        else:
            draw_block(p, body, fill, UI_BORDER, self.BORDER, self.SHADOW)
            if self.hasFocus():
                pen = QPen(QColor(fg), 1, Qt.PenStyle.DotLine)
                p.setPen(pen)
                p.drawRect(body.adjusted(self.BORDER + 3, self.BORDER + 3,
                                         -self.BORDER - 4, -self.BORDER - 4))
        p.setPen(QColor(fg))
        p.setFont(self.font())
        p.drawText(body.adjusted(self.BORDER + 4, 0, -self.BORDER - 4, 0),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.text())


class PixelCard(QAbstractButton):
    """Clickable card: a pixel-font title over lines of body text; turns dark on hover/select."""

    SHADOW = 3
    BORDER = 3
    PAD = 16
    TITLE_PX = 14
    BODY_PX = 20

    def __init__(self, title: str, lines: List[str], title_color: str = UI_INK, parent=None):
        super().__init__(parent)
        self.title = title
        self.lines = list(lines)
        self.title_color = title_color
        self.setText(title)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_lines(self, lines: List[str]):
        self.lines = list(lines)
        self.updateGeometry()
        self.update()

    def _body_line_height(self) -> int:
        return int(terminal_font(self.BODY_PX).pixelSize() * 1.05)

    def sizeHint(self) -> QSize:
        title_h = self.TITLE_PX + 14
        body_h = self._body_line_height() * len(self.lines)
        extra = 2 * self.BORDER + self.SHADOW + 2 * self.PAD
        return QSize(220, title_h + body_h + extra)

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.sizeHint().height())

    def paintEvent(self, event):
        p = QPainter(self)
        dark = self.isChecked() or self.isDown() or self.underMouse()
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        if self.isDown():
            body.translate(self.SHADOW, self.SHADOW)
            draw_block(p, body, UI_INK, UI_BORDER, self.BORDER)
        else:
            draw_block(p, body, UI_INK if dark else UI_CARD, UI_BORDER, self.BORDER, self.SHADOW)
            if self.hasFocus() and not dark:
                p.setPen(QPen(QColor(UI_INNER), 1, Qt.PenStyle.DotLine))
                p.drawRect(body.adjusted(self.BORDER + 3, self.BORDER + 3,
                                         -self.BORDER - 4, -self.BORDER - 4))
        inner = body.adjusted(self.BORDER + self.PAD, self.BORDER + self.PAD - 2,
                              -self.BORDER - self.PAD, -self.BORDER - self.PAD)
        p.setFont(pixel_font(self.TITLE_PX))
        p.setPen(QColor(UI_LIME if dark else self.title_color))
        p.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.title)
        p.setFont(terminal_font(self.BODY_PX))
        p.setPen(QColor(UI_LIME_DIM if dark else UI_BORDER))
        y = inner.top() + self.TITLE_PX + 14
        step = self._body_line_height()
        for line in self.lines:
            p.drawText(QRect(inner.left(), y, inner.width(), step),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
            y += step
