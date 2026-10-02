import math
from typing import List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from algorithms.planar_puzzle import (Edge, Measure, PlanarPuzzle, Point, conflicts,
                                      enclosed_faces, measure)
from core.constants import (CONFLICT_EDGE_STROKE, DEFAULT_EDGE_STROKE, DEFAULT_NODE_FILL,
                            DEFAULT_NODE_STROKE, EDGE_CONFLICT_STROKE_WIDTH, EDGE_STROKE_WIDTH,
                            NODE_STROKE_WIDTH, UI_BORDER, UI_DOT, UI_FIELD, UI_INNER, UI_LIME,
                            UI_PANEL)
from ui.accessories import draw_vertex_icon
from ui.fonts import body_font
from ui.styles import SIZE_BODY
from ui.widgets.pixel import dot_tile

MARGIN = 36
STEPS = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
         Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}


def draw_vertex(painter: QPainter, centre: QPointF, radius: float, fill: str,
                stroke_width: float = NODE_STROKE_WIDTH, plain: bool = False):
    if not plain and draw_vertex_icon(painter, centre, radius, fill):
        return
    painter.setPen(QPen(QColor(DEFAULT_NODE_STROKE), stroke_width))
    painter.setBrush(QColor(fill))
    painter.drawEllipse(centre, radius, radius)


class GridPaper(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(480, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.puzzle: Optional[PlanarPuzzle] = None
        self.pos: List[Point] = []
        self.bad: Set[int] = set()
        self.selected: Optional[int] = None
        self.dragging = False
        self.locked = False
        self._tile = dot_tile(UI_PANEL, UI_INNER)

    def load(self, puzzle: PlanarPuzzle):
        self.puzzle = puzzle
        self.pos = list(puzzle.start)
        self.selected, self.dragging = None, False
        self.refresh()

    def reset(self):
        if self.puzzle is not None:
            self.pos = list(self.puzzle.start)
            self.dragging = False
            self.refresh()

    def set_positions(self, pos: Sequence[Point]):
        self.pos = list(pos)
        self.refresh()

    def refresh(self):
        self.bad = conflicts(self.puzzle.edges, self.pos) if self.puzzle else set()
        self.update()
        self.changed.emit()

    def is_planar(self) -> bool:
        return self.puzzle is not None and not self.bad

    def measure(self) -> Optional[Measure]:
        if not self.is_planar():
            return None
        return measure(self.puzzle.n, self.puzzle.edges, self.pos)

    def frame(self) -> Tuple[float, float, float]:
        cols, rows = (self.puzzle.cols, self.puzzle.rows) if self.puzzle else (12, 8)
        cell = max(4.0, min((self.width() - 2 * MARGIN) / cols, (self.height() - 2 * MARGIN) / rows))
        return cell, (self.width() - cell * cols) / 2, (self.height() - cell * rows) / 2

    def point(self, p: Point) -> QPointF:
        cell, x0, y0 = self.frame()
        return QPointF(x0 + p[0] * cell, y0 + p[1] * cell)

    def nearest(self, where: QPointF) -> Point:
        cell, x0, y0 = self.frame()
        return (max(0, min(self.puzzle.cols, round((where.x() - x0) / cell))),
                max(0, min(self.puzzle.rows, round((where.y() - y0) / cell))))

    def vertex_at(self, where: QPointF) -> Optional[int]:
        reach = self.frame()[0] * 0.45
        for v, p in enumerate(self.pos):
            centre = self.point(p)
            if math.hypot(where.x() - centre.x(), where.y() - centre.y()) <= reach:
                return v
        return None

    def slide(self, target: Point) -> bool:
        v = self.selected
        if v is None or self.locked:
            return False
        moved = False
        while self.pos[v] != target:
            x, y = self.pos[v]
            dx, dy = target[0] - x, target[1] - y
            steps = [(x + (dx > 0) - (dx < 0), y), (x, y + (dy > 0) - (dy < 0))]
            if abs(dy) > abs(dx):
                steps.reverse()
            step = next((s for s in steps if s != (x, y) and s not in self.pos), None)
            if step is None:
                break
            self.pos[v] = step
            moved = True
        if moved:
            self.refresh()
        return moved

    def mousePressEvent(self, event):
        if self.locked or self.puzzle is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        v = self.vertex_at(event.position())
        if v is not None:
            self.selected, self.dragging = v, True
            self.update()

    def mouseMoveEvent(self, event):
        if self.puzzle is None:
            return
        if self.dragging and not self.locked:
            self.slide(self.nearest(event.position()))
            return
        over = not self.locked and self.vertex_at(event.position()) is not None
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def keyPressEvent(self, event):
        step = STEPS.get(event.key())
        if step is None or self.selected is None or self.locked or self.puzzle is None:
            super().keyPressEvent(event)
            return
        x, y = self.pos[self.selected]
        target = (x + step[0], y + step[1])
        if 0 <= target[0] <= self.puzzle.cols and 0 <= target[1] <= self.puzzle.rows:
            self.slide(target)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QBrush(self._tile))
        if self.puzzle is None:
            return
        puzzle = self.puzzle
        cell, x0, y0 = self.frame()
        paper = QRectF(x0, y0, cell * puzzle.cols, cell * puzzle.rows)
        painter.fillRect(paper.adjusted(-3, -3, 3, 3), QColor(UI_BORDER))
        painter.fillRect(paper, QColor(UI_FIELD))
        painter.setPen(QPen(QColor(UI_DOT), 1))
        for c in range(1, puzzle.cols):
            painter.drawLine(self.point((c, 0)), self.point((c, puzzle.rows)))
        for r in range(1, puzzle.rows):
            painter.drawLine(self.point((0, r)), self.point((puzzle.cols, r)))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.bad:
            shade = QColor(UI_LIME)
            shade.setAlpha(120)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shade)
            for walk in enclosed_faces(puzzle.n, puzzle.edges, self.pos):
                painter.drawPolygon(QPolygonF([self.point(self.pos[v]) for v in walk]))
            xs, ys = [p[0] for p in self.pos], [p[1] for p in self.pos]
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(UI_BORDER), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(self.point((min(xs), min(ys))), self.point((max(xs), max(ys)))))
        for i, (a, b) in enumerate(puzzle.edges):
            if i in self.bad:
                painter.setPen(QPen(QColor(CONFLICT_EDGE_STROKE), EDGE_CONFLICT_STROKE_WIDTH))
            else:
                painter.setPen(QPen(QColor(DEFAULT_EDGE_STROKE), EDGE_STROKE_WIDTH))
            painter.drawLine(self.point(self.pos[a]), self.point(self.pos[b]))
        radius = max(7.0, min(16.0, cell * 0.24))
        for v, p in enumerate(self.pos):
            draw_vertex(painter, self.point(p), radius,
                        UI_LIME if v == self.selected else DEFAULT_NODE_FILL)


class LayoutThumb(QWidget):
    def __init__(self, edges: Sequence[Edge], pos: Optional[Sequence[Point]],
                 empty_text: str = "NOT SOLVED", parent=None):
        super().__init__(parent)
        self.edges = list(edges)
        self.pos = list(pos) if pos is not None else None
        self.empty_text = empty_text
        self.setFixedSize(self.sizeHint())

    def sizeHint(self) -> QSize:
        return QSize(220, 150)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(UI_BORDER))
        painter.fillRect(self.rect().adjusted(3, 3, -3, -3), QColor(UI_FIELD))
        if self.pos is None:
            painter.setFont(body_font(SIZE_BODY))
            painter.setPen(QColor(UI_INNER))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.empty_text)
            return
        xs, ys = [p[0] for p in self.pos], [p[1] for p in self.pos]
        w, h = max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys))
        cell = min((self.width() - 44) / w, (self.height() - 44) / h, 44.0)
        x0, y0 = (self.width() - w * cell) / 2, (self.height() - h * cell) / 2

        def point(p: Point) -> QPointF:
            return QPointF(x0 + (p[0] - min(xs)) * cell, y0 + (p[1] - min(ys)) * cell)

        painter.setPen(QPen(QColor(UI_DOT), 1))
        for c in range(w + 1):
            painter.drawLine(point((min(xs) + c, min(ys))), point((min(xs) + c, max(ys))))
        for r in range(h + 1):
            painter.drawLine(point((min(xs), min(ys) + r)), point((max(xs), min(ys) + r)))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(DEFAULT_EDGE_STROKE), 2))
        for a, b in self.edges:
            painter.drawLine(point(self.pos[a]), point(self.pos[b]))
        for p in self.pos:
            draw_vertex(painter, point(p), 5, DEFAULT_NODE_FILL, 2)
