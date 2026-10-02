from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QGraphicsEllipseItem, QGraphicsLineItem,
                               QGraphicsRectItem, QGraphicsSimpleTextItem)

from algorithms.coloring import edge_key
from core.constants import (CONFLICT_EDGE_STROKE, DEFAULT_EDGE_STROKE, DEFAULT_NODE_FILL,
                            DEFAULT_NODE_STROKE, EDGE_CONFLICT_STROKE_WIDTH, EDGE_STROKE_WIDTH,
                            HINT_HALO_COLOR, HOVER_GLOW_BLUR, HOVER_GLOW_COLOR, NODE_STROKE_WIDTH,
                            PALETTE, UI_PANEL)
from ui import accessories
from ui.fonts import body_font, pixel_font
from ui.widgets.color_palette import text_color_for

Z_EDGE, Z_CONFLICT_EDGE, Z_HALO, Z_VERTEX, Z_BADGE = 0, 0.5, 1, 2, 3


def vertex_label(index: int) -> str:
    label = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def _centered_text(parent, text: str, font, color: str) -> QGraphicsSimpleTextItem:
    item = QGraphicsSimpleTextItem(text, parent)
    item.setFont(font)
    item.setBrush(QBrush(QColor(color)))
    rect = item.boundingRect()
    item.setPos(-rect.width() / 2, -rect.height() / 2)
    item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
    return item


class VertexItem(QGraphicsEllipseItem):
    def __init__(self, x: float, y: float, radius: float, vertex_id: int, label: str = ""):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.setPos(x, y)
        self.vertex_id = vertex_id
        self.radius = radius
        self.color_index: Optional[int] = None
        self.setBrush(QBrush(QColor(DEFAULT_NODE_FILL)))
        self.setPen(QPen(QColor(DEFAULT_NODE_STROKE), NODE_STROKE_WIDTH))
        self.setZValue(Z_VERTEX)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font_px = max(10, round(radius * (1.45 if len(label) < 2 else 1.1)))
        plain = accessories.vertex_icon_bounds(radius) is None
        self.label_item = _centered_text(self, label, body_font(font_px, crisp=False),
                                         text_color_for(DEFAULT_NODE_FILL)) if label and plain else None

    def icon_rect(self) -> Optional[QRectF]:
        size = accessories.vertex_icon_bounds(self.radius)
        if size is None:
            return None
        return QRectF(-size[0] / 2, -size[1] / 2, size[0], size[1])

    def boundingRect(self) -> QRectF:
        rect, icon = super().boundingRect(), self.icon_rect()
        return rect if icon is None else rect.united(icon)

    def shape(self) -> QPainterPath:
        path, size = super().shape(), accessories.vertex_icon_size(self.radius)
        if size is not None:
            path.addRect(QRectF(-size[0] / 2, -size[1] / 2, size[0], size[1]))
        return path

    def paint(self, painter, option, widget=None):
        if not accessories.draw_vertex_icon(painter, QPointF(0, 0), self.radius,
                                            self.brush().color().name()):
            super().paint(painter, option, widget)

    def set_color(self, color_index: Optional[int]):
        self.color_index = color_index
        fill = DEFAULT_NODE_FILL if color_index is None else PALETTE[color_index]
        self.setBrush(QBrush(QColor(fill)))
        self.setPen(QPen(QColor(DEFAULT_NODE_STROKE), NODE_STROKE_WIDTH))
        if self.label_item is not None:
            self.label_item.setBrush(QBrush(QColor(text_color_for(fill))))

    def fill_color(self) -> str:
        return self.brush().color().name().upper()

    def hoverEnterEvent(self, event):
        glow = QGraphicsDropShadowEffect()
        glow.setColor(QColor(HOVER_GLOW_COLOR))
        glow.setBlurRadius(HOVER_GLOW_BLUR)
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setGraphicsEffect(None)
        super().hoverLeaveEvent(event)


class EdgeItem(QGraphicsLineItem):
    def __init__(self, x1: float, y1: float, x2: float, y2: float, u: int, v: int):
        super().__init__(x1, y1, x2, y2)
        self.u = u
        self.v = v
        self.key = edge_key(u, v)
        self.is_conflict = False
        self.setZValue(Z_EDGE)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setPen(QPen(QColor(DEFAULT_EDGE_STROKE), EDGE_STROKE_WIDTH))

        self.tag = QGraphicsRectItem(self)
        text = _centered_text(self.tag, "CONFLICT!", pixel_font(12, crisp=False), CONFLICT_EDGE_STROKE)
        box = text.mapRectToParent(text.boundingRect()).adjusted(-3, -2, 3, 2)
        self.tag.setRect(box)
        self.tag.setBrush(QBrush(QColor(UI_PANEL)))
        self.tag.setPen(QPen(Qt.PenStyle.NoPen))
        self.tag.setPos((x1 + x2) / 2, (y1 + y2) / 2)
        self.tag.setVisible(False)

    def set_conflict(self, is_conflict: bool):
        if is_conflict == self.is_conflict:
            return
        self.is_conflict = is_conflict
        self.tag.setVisible(is_conflict)
        self.setZValue(Z_CONFLICT_EDGE if is_conflict else Z_EDGE)
        if is_conflict:
            self.setPen(QPen(QColor(CONFLICT_EDGE_STROKE), EDGE_CONFLICT_STROKE_WIDTH))
        else:
            self.setPen(QPen(QColor(DEFAULT_EDGE_STROKE), EDGE_STROKE_WIDTH))


class HintHaloItem(QGraphicsEllipseItem):
    def __init__(self, x: float, y: float, radius: float):
        r = radius + 7
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.setPos(x, y)
        pen = QPen(QColor(HINT_HALO_COLOR), 4)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setBrush(QBrush(QColor(255, 255, 255, 110)))
        self.setZValue(Z_HALO)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


class SuggestionBadgeItem(QGraphicsEllipseItem):
    def __init__(self, x: float, y: float, radius: float, color_index: int):
        r = max(5.0, radius * 0.6)
        super().__init__(-r, -r, 2 * r, 2 * r)
        self.setPos(x + radius + r * 0.4, y - radius - r * 0.4)
        self.color_index = color_index
        self.setBrush(QBrush(QColor(PALETTE[color_index])))
        self.setPen(QPen(QColor(DEFAULT_NODE_STROKE), 2))
        self.setZValue(Z_BADGE)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
