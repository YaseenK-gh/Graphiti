from typing import List, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QFrame, QPushButton, QSizePolicy, QWidget

from core.constants import (UI_BG, UI_BORDER, UI_BUTTON, UI_CARD, UI_DANGER_BG, UI_DANGER_TEXT,
                            UI_DARK_LINE, UI_DOT, UI_EASY, UI_INK, UI_INNER, UI_LIME, UI_LIME_DIM,
                            UI_PANEL)
from ui import fonts
from ui.fonts import body_font, pixel_font
from ui.styles import (SIZE_BUTTON, SIZE_BUTTON_SMALL, SIZE_SUBTITLE, line_height_px,
                       size_body)


def draw_block(p: QPainter, rect: QRect, fill: str, border: str = UI_BORDER, border_w: int = 3,
               shadow: int = 0, inner: Optional[str] = None):
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tile = dot_tile(UI_BG, UI_DOT)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawTiledPixmap(self.rect(), self._tile)


class PixelPanel(QFrame):
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


BUTTON_VARIANTS = {
    "light": (UI_BUTTON, UI_INK, UI_INK, UI_BG, UI_INK, UI_BG),
    "card": (UI_CARD, UI_INK, UI_INK, UI_BG, UI_INK, UI_BG),
    "dark": (UI_DARK_LINE, UI_LIME_DIM, UI_LIME, UI_INK, UI_LIME, UI_INK),
    "danger": (UI_DANGER_BG, UI_DANGER_TEXT, UI_DANGER_TEXT, UI_INK, UI_DANGER_TEXT, UI_INK),
    "tab": (UI_DARK_LINE, UI_LIME_DIM, UI_EASY, UI_INK, UI_LIME, UI_INK),
}


class PixelButton(QPushButton):
    SHADOW = 3
    BORDER = 3

    def __init__(self, text: str = "", variant: str = "light", small: bool = False,
                 icon: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.icon_name = icon
        self.pad_x, self.pad_y = (8, 8) if small else (16, 12)
        px = SIZE_BUTTON_SMALL if small else SIZE_BUTTON
        self.setFont(pixel_font(px))
        self.setStyleSheet(f"font-family: '{fonts.PIXEL}'; font-size: {px}px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_variant(self, variant: str):
        self.variant = variant
        self.update()

    def _icon_cell(self) -> int:
        return max(1, round(self.font().pixelSize() / 7))

    def _icon_width(self) -> int:
        if not self.icon_name:
            return 0
        return len(GLYPHS[self.icon_name][0]) * self._icon_cell() + self.font().pixelSize()

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        extra = 2 * self.BORDER + self.SHADOW
        return QSize(fm.horizontalAdvance(self.text()) + self._icon_width() + 2 * self.pad_x + extra,
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
        p.setPen(QColor(fg))
        p.setFont(self.font())
        if not self.icon_name:
            p.drawText(body.adjusted(self.BORDER + 4, 0, -self.BORDER - 4, 0),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.text())
            return
        cell = self._icon_cell()
        rows = GLYPHS[self.icon_name]
        text_w = self.fontMetrics().horizontalAdvance(self.text())
        total = self._icon_width() + text_w
        x = body.center().x() - total // 2 + 1
        draw_bitmap(p, rows, x, body.center().y() - len(rows) * cell // 2 + 1, cell, fg)
        x += self._icon_width()
        p.drawText(QRect(x, body.top(), text_w + 2, body.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class PixelCard(QAbstractButton):
    SHADOW = 3
    BORDER = 3
    PAD = 16
    TITLE_PX = SIZE_SUBTITLE

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
        return line_height_px(size_body())

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
        inner = body.adjusted(self.BORDER + self.PAD, self.BORDER + self.PAD - 2,
                              -self.BORDER - self.PAD, -self.BORDER - self.PAD)
        p.setFont(pixel_font(self.TITLE_PX))
        p.setPen(QColor(UI_LIME if dark else self.title_color))
        p.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.title)
        p.setFont(body_font(size_body()))
        p.setPen(QColor(UI_LIME_DIM if dark else UI_BORDER))
        y = inner.top() + self.TITLE_PX + 14
        step = self._body_line_height()
        for line in self.lines:
            p.drawText(QRect(inner.left(), y, inner.width(), step),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
            y += step


def draw_bitmap(p: QPainter, rows: List[str], x: int, y: int, cell: int, color: str):
    qcolor = QColor(color)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                p.fillRect(x + c * cell, y + r * cell, cell, cell, qcolor)


def icon_pixmap(name: str, color: str, cell: int = 2) -> QPixmap:
    rows = GLYPHS.get(name) or ICONS[name]
    pixmap = QPixmap(len(rows[0]) * cell, len(rows) * cell)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_bitmap(painter, rows, 0, 0, cell, color)
    painter.end()
    return pixmap


GLYPHS = {
    "play": ["#......", "###....", "#####..", "#######", "#####..", "###....", "#......"],
    "back": ["......#", "....###", "..#####", "#######", "..#####", "....###", "......#"],
    "star": ["...#...", "..###..", "#######", ".#####.", "..###..", ".##.##.", "##...##"],
    "star_outline": ["...#...", "..#.#..", "###.###", ".#...#.", "..#.#..", ".#.#.#.", "##...##"],
    "close": ["##...##", ".##.##.", "..###..", "...#...", "..###..", ".##.##.", "##...##"],
    "gem": ["...#...", "..###..", ".#####.", "#######", ".#####.", "..###..", "...#..."],
    "net": ["..###..", "..###..", "...#...", "..#.#..", ".#...#.", "###.###", "###.###"],
}

ICONS = {
    "guide": [
        "............",
        ".#########..",
        ".##.......#.",
        ".##.####..#.",
        ".##.......#.",
        ".##.####..#.",
        ".##.......#.",
        ".##.......#.",
        ".##########.",
        ".#........#.",
        ".##########.",
        "............",
    ],
    "trophy": [
        "............",
        ".##########.",
        "##.######.##",
        "#..######..#",
        "##.######.##",
        "..########..",
        "...######...",
        "....####....",
        ".....##.....",
        ".....##.....",
        "...######...",
        "...######...",
    ],
    "sound": [
        "............",
        ".....#......",
        "....##...#..",
        "..####....#.",
        ".#####.#..#.",
        ".#####..#.#.",
        ".#####..#.#.",
        ".#####.#..#.",
        "..####....#.",
        "....##...#..",
        ".....#......",
        "............",
    ],
    "muted": [
        "............",
        ".....#......",
        "....##......",
        "..####.#...#",
        ".#####..#.#.",
        ".#####...#..",
        ".#####..#.#.",
        ".#####.#...#",
        "..####......",
        "....##......",
        ".....#......",
        "............",
    ],
}


class PixelIconButton(QAbstractButton):
    SHADOW = 3
    BORDER = 3
    SIZE = 60

    def __init__(self, icon: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.icon_name = icon
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.SIZE, self.SIZE)

    def set_icon(self, icon: str):
        self.icon_name = icon
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        fill, fg, hover_fill, hover_fg, down_fill, down_fg = BUTTON_VARIANTS["light"]
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        if self.isDown():
            body.translate(self.SHADOW, self.SHADOW)
            draw_block(p, body, down_fill, UI_BORDER, self.BORDER)
            fg = down_fg
        elif self.underMouse():
            draw_block(p, body, hover_fill, UI_BORDER, self.BORDER, self.SHADOW)
            fg = hover_fg
        else:
            draw_block(p, body, fill, UI_BORDER, self.BORDER, self.SHADOW)
        rows = ICONS[self.icon_name]
        cell = max(1, (min(body.width(), body.height()) - 2 * self.BORDER - 12) // len(rows))
        draw_bitmap(p, rows, body.center().x() - cell * len(rows[0]) // 2 + 1,
                    body.center().y() - cell * len(rows) // 2 + 1, cell, fg)


class PixelTitle(QWidget):
    def __init__(self, text: str, px: int, color: str = UI_INK, shadow: str = UI_INNER,
                 gap_units: int = 2, parent=None):
        super().__init__(parent)
        self.text = text
        self.px = px
        self.unit = max(1, px // 8)
        self.gap = self.unit * gap_units
        self.color, self.shadow = color, shadow
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _glyphs(self):
        fm = QFontMetrics(pixel_font(self.px))
        return [(ch, fm.tightBoundingRect(ch)) if ch.strip() else (ch, QRect(0, 0, fm.horizontalAdvance(ch), 0))
                for ch in self.text]

    def _ink_width(self, glyphs) -> int:
        return sum(r.width() for _, r in glyphs) + self.gap * (len(glyphs) - 1)

    def sizeHint(self) -> QSize:
        return QSize(self._ink_width(self._glyphs()) + self.unit, self.px + self.unit + 4)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setFont(pixel_font(self.px))
        glyphs = self._glyphs()
        left = (self.width() - self._ink_width(glyphs) - self.unit) // 2
        baseline = (self.height() - self.unit + QFontMetrics(p.font()).ascent()) // 2
        for offset, color in ((self.unit, self.shadow), (0, self.color)):
            p.setPen(QColor(color))
            x = left
            for ch, r in glyphs:
                if ch.strip():
                    p.drawText(x - r.left() + offset, baseline + offset, ch)
                x += r.width() + self.gap
