"""Interactive graph view: rendering, coloring by mouse, conflict display, zoom/pan, hints."""

import gc
import math
from typing import Callable, Dict, List, Optional, Set

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView

from algorithms.coloring import count_distinct_colors, detect_conflicts
from algorithms.layouts import vertex_radius
from core.constants import (CANVAS_HEIGHT, CANVAS_WIDTH, SOLUTION_ANIMATION_MS, UI_BORDER, UI_INNER,
                            UI_PANEL)
from core.game_state import Graph
from ui.fonts import pixel_font
from ui.widgets.graph_items import (EdgeItem, HintHaloItem, SuggestionBadgeItem, VertexItem,
                                    vertex_label)
from ui.widgets.pixel import dot_tile

MIN_ZOOM, MAX_ZOOM = 0.5, 3.0


class GraphCanvas(QGraphicsView):
    """Left-click colors a vertex with the active color, right-click erases it."""

    coloring_changed = Signal()   # Any vertex color changed.
    graph_completed = Signal()    # Every vertex colored and no conflicts.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graph_scene = QGraphicsScene(self)
        self.graph_scene.setSceneRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
        self.setScene(self.graph_scene)
        self.setBackgroundBrush(QBrush(dot_tile(UI_PANEL, UI_INNER)))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.graph: Optional[Graph] = None
        self.coloring: Dict[int, Optional[int]] = {}
        self.conflicts: Set[str] = set()
        self.active_color = 0
        self.vertex_radius = 10.0
        self.vertex_items: Dict[int, VertexItem] = {}
        self.edge_items: Dict[str, EdgeItem] = {}
        self.interactive = True

        self.pan_start = None
        self.zoom_factor = 1.0

        self.hint_vertex: Optional[int] = None
        self._hint_halo: Optional[HintHaloItem] = None
        self._hint_badge: Optional[SuggestionBadgeItem] = None
        self._hint_anim: Optional[QVariantAnimation] = None

        self._anim_timer: Optional[QTimer] = None
        self._anim_queue: List[int] = []
        self._anim_solution: Dict[int, int] = {}
        self._anim_done: Optional[Callable[[], None]] = None

    # ─── Loading ──────────────────────────────────────────────────────────────

    def set_graph(self, graph: Graph, coloring: Optional[Dict[int, Optional[int]]] = None):
        """Load a graph, with explicit cleanup of the previous one.

        Pass `coloring` to share a dict with the game state; it is reset in place.
        """
        self.stop_animation()
        self.clear_scene()
        self.graph = graph
        self.vertex_radius = vertex_radius(graph.n)
        self.coloring = coloring if coloring is not None else {}
        self.coloring.clear()
        self.coloring.update({v: None for v in graph.vertices})
        self.conflicts = set()
        self.interactive = True
        self.draw_graph()
        self.reset_zoom()

    def clear_scene(self):
        """Remove every item from the scene and release references."""
        self.clear_hint()
        for item in list(self.edge_items.values()) + list(self.vertex_items.values()):
            self.graph_scene.removeItem(item)
        self.vertex_items.clear()
        self.edge_items.clear()
        self.graph_scene.clear()
        gc.collect()

    def draw_graph(self):
        """Edges first (back layer), then vertices on top."""
        if not self.graph:
            return
        layout = self.graph.layout
        for u, v in self.graph.edges:
            (x1, y1), (x2, y2) = layout[u], layout[v]
            item = EdgeItem(x1, y1, x2, y2, u, v)
            self.graph_scene.addItem(item)
            self.edge_items[item.key] = item
        for v in self.graph.vertices:
            x, y = layout[v]
            item = VertexItem(x, y, self.vertex_radius, v, vertex_label(v))
            self.graph_scene.addItem(item)
            self.vertex_items[v] = item
        if self.graph.type in ('BIPARTITE', 'COMPLETE_BIPARTITE'):
            self.draw_side_labels()
        self.update_conflicts()

    def draw_side_labels(self):
        """'SET A' / 'SET B' above the two columns of a bipartite layout."""
        half = self.graph.n // 2
        for name, side in (("SET A", range(half)), ("SET B", range(half, self.graph.n))):
            points = [self.graph.layout[v] for v in side]
            if not points:
                continue
            x = sum(p[0] for p in points) / len(points)
            top = min(p[1] for p in points)
            text = self.graph_scene.addSimpleText(name, pixel_font(12))
            text.setBrush(QColor(UI_BORDER))
            rect = text.boundingRect()
            text.setPos(x - rect.width() / 2, top - self.vertex_radius - rect.height() - 8)

    # ─── Coloring ─────────────────────────────────────────────────────────────

    def set_active_color(self, color_index: int):
        self.active_color = color_index

    def color_vertex(self, vertex_id: int, color_index: Optional[int] = None):
        """Color a vertex (default: the active color). Emits graph_completed when solved."""
        if not self.interactive or self.graph is None or vertex_id not in self.vertex_items:
            return
        color_index = self.active_color if color_index is None else color_index
        self._apply_color(vertex_id, color_index)
        if vertex_id == self.hint_vertex:
            self.clear_hint()
        self.update_conflicts()
        self.coloring_changed.emit()
        if self.is_complete():
            self.graph_completed.emit()

    def erase_vertex(self, vertex_id: int):
        if not self.interactive or self.graph is None or vertex_id not in self.vertex_items:
            return
        if self.coloring.get(vertex_id) is None:
            return
        self._apply_color(vertex_id, None)
        self.update_conflicts()
        self.coloring_changed.emit()

    def clear_coloring(self):
        """Erase every vertex (level reset)."""
        self.stop_animation()
        self.clear_hint()
        for v in self.vertex_items:
            self._apply_color(v, None)
        self.interactive = True
        self.update_conflicts()
        self.coloring_changed.emit()

    def _apply_color(self, vertex_id: int, color_index: Optional[int]):
        self.coloring[vertex_id] = color_index
        self.vertex_items[vertex_id].set_color(color_index)

    def update_conflicts(self):
        """Recompute conflicting edges and paint them red."""
        if self.graph is None:
            return
        self.conflicts = detect_conflicts(self.coloring, self.graph.edges)
        for key, item in self.edge_items.items():
            item.set_conflict(key in self.conflicts)

    def colored_count(self) -> int:
        return sum(1 for c in self.coloring.values() if c is not None)

    def colors_used(self) -> int:
        return count_distinct_colors(self.coloring)

    def is_complete(self) -> bool:
        return (self.graph is not None and not self.conflicts
                and all(self.coloring.get(v) is not None for v in self.graph.vertices))

    # ─── Hints ────────────────────────────────────────────────────────────────

    def highlight_vertex(self, vertex_id: int, color_index: Optional[int] = None):
        """Pulsing halo on a vertex, plus a swatch of the suggested color if given."""
        self.clear_hint()
        item = self.vertex_items.get(vertex_id)
        if item is None:
            return
        self.hint_vertex = vertex_id
        pos = item.pos()
        self._hint_halo = HintHaloItem(pos.x(), pos.y(), self.vertex_radius)
        self.graph_scene.addItem(self._hint_halo)
        halo = self._hint_halo
        anim = QVariantAnimation(self)
        anim.setStartValue(0.25)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setEndValue(0.25)
        anim.setDuration(900)
        anim.setLoopCount(-1)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.valueChanged.connect(halo.setOpacity)
        anim.start()
        self._hint_anim = anim
        if color_index is not None:
            self.show_hint_color_suggestion(vertex_id, color_index)

    def show_hint_color_suggestion(self, vertex_id: int, color_index: int):
        if self._hint_badge is not None:
            self.graph_scene.removeItem(self._hint_badge)
        pos = self.vertex_items[vertex_id].pos()
        self._hint_badge = SuggestionBadgeItem(pos.x(), pos.y(), self.vertex_radius, color_index)
        self.graph_scene.addItem(self._hint_badge)

    def clear_hint(self):
        if self._hint_anim is not None:
            self._hint_anim.stop()
            self._hint_anim.deleteLater()
            self._hint_anim = None
        for item in (self._hint_halo, self._hint_badge):
            if item is not None and item.scene() is self.graph_scene:
                self.graph_scene.removeItem(item)
        self._hint_halo = None
        self._hint_badge = None
        self.hint_vertex = None

    # ─── Solution animation (forfeit) ─────────────────────────────────────────

    def animate_solution(self, solution: Dict[int, int], duration_ms: int = SOLUTION_ANIMATION_MS,
                         on_finished: Optional[Callable[[], None]] = None):
        """Color vertices one by one over `duration_ms`, then call `on_finished`."""
        self.stop_animation()
        self.clear_hint()
        self.interactive = False
        self._anim_solution = dict(solution)
        self._anim_queue = sorted(solution)
        self._anim_done = on_finished
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(max(10, duration_ms // max(1, len(self._anim_queue))))
        self._anim_timer.timeout.connect(self._animation_step)
        self._anim_timer.start()

    def _animation_step(self):
        if self._anim_queue:
            v = self._anim_queue.pop(0)
            self._apply_color(v, self._anim_solution[v])
            self.update_conflicts()
        if not self._anim_queue:
            done = self._anim_done
            self.stop_animation()
            self.coloring_changed.emit()
            if done:
                done()

    def stop_animation(self):
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer.deleteLater()
            self._anim_timer = None
        self._anim_queue = []
        self._anim_done = None

    def is_animating(self) -> bool:
        return self._anim_timer is not None

    # ─── Mouse & view ─────────────────────────────────────────────────────────

    def vertex_at(self, scene_pos: QPointF) -> Optional[int]:
        """Nearest vertex under the cursor, with a few pixels of slack for small nodes."""
        scale = self.transform().m11() or 1.0
        reach = self.vertex_radius + 4.0 / scale
        best, best_d = None, reach
        for v, item in self.vertex_items.items():
            p = item.pos()
            d = math.hypot(p.x() - scene_pos.x(), p.y() - scene_pos.y())
            if d <= best_d:
                best, best_d = v, d
        return best

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        vertex = self.vertex_at(self.mapToScene(event.position().toPoint()))
        if vertex is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.color_vertex(vertex)
            elif event.button() == Qt.MouseButton.RightButton:
                self.erase_vertex(vertex)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pan_start is not None:
            delta = event.position() - self.pan_start
            self.pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self.pan_start is not None:
            self.pan_start = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Zoom around the cursor, clamped relative to the fitted view."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = self.zoom_factor * factor
        if MIN_ZOOM <= new_zoom <= MAX_ZOOM:
            self.zoom_factor = new_zoom
            self.scale(factor, factor)
        event.accept()

    def reset_zoom(self):
        """Fit the graph (not the whole scene) so it fills the canvas; small graphs zoom at most 2×."""
        self.resetTransform()
        self.zoom_factor = 1.0
        scene_rect = self.graph_scene.sceneRect()
        target = self.graph_scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
        if target.isEmpty():
            target = scene_rect
        min_w, min_h = scene_rect.width() / 2, scene_rect.height() / 2
        if target.width() < min_w or target.height() < min_h:
            center = target.center()
            target.setWidth(max(target.width(), min_w))
            target.setHeight(max(target.height(), min_h))
            target.moveCenter(center)
        self.fitInView(target, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reset_zoom()

    def showEvent(self, event):
        super().showEvent(event)
        self.reset_zoom()
