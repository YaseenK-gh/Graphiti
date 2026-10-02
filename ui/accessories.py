import math
import os
from functools import lru_cache
from typing import Optional, Tuple

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPixmap

from core.accessories import ASSET_DIR, CURSOR, DEFAULT, VERTEX, Wallet, find
from core.constants import DEFAULT_NODE_STROKE
from core.storage import load_json

CURSOR_TARGET_PX = 36
ICON_FILL_RATIO = 1.5

_state = {"vertex": DEFAULT, "cursor": DEFAULT, "override": False}


@lru_cache(maxsize=None)
def source_image(kind: str, item_id: str) -> Optional[QImage]:
    item = find(kind, item_id)
    if item is None or item.path is None or not os.path.exists(item.path):
        return None
    image = QImage(item.path).convertToFormat(QImage.Format.Format_ARGB32)
    return None if image.isNull() else image


def _scaled(image: QImage, scale: int) -> QPixmap:
    return QPixmap.fromImage(image.scaled(image.width() * scale, image.height() * scale,
                                          Qt.AspectRatioMode.IgnoreAspectRatio,
                                          Qt.TransformationMode.FastTransformation))


@lru_cache(maxsize=512)
def vertex_pixmap(item_id: str, fill: str, scale: int) -> Optional[QPixmap]:
    source = source_image(VERTEX, item_id)
    if source is None:
        return None
    image = source.copy()
    ink, tint = QColor(DEFAULT_NODE_STROKE).rgba(), QColor(fill).rgba()
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            if pixel.alpha() == 0:
                continue
            if pixel.red() < 64:
                image.setPixel(x, y, ink)
            elif pixel.red() < 200:
                image.setPixel(x, y, tint)
    return _scaled(image, scale)


def vertex_icon() -> str:
    return _state["vertex"]


def set_vertex_icon(item_id: str):
    _state["vertex"] = item_id if source_image(VERTEX, item_id) is not None else DEFAULT


def icon_scale(item_id: str, radius: float) -> int:
    source = source_image(VERTEX, item_id)
    cells = max(source.width(), source.height())
    return max(1, int(2 * radius * ICON_FILL_RATIO / cells + 0.4))


def vertex_icon_size(radius: float) -> Optional[Tuple[int, int]]:
    item_id = vertex_icon()
    source = source_image(VERTEX, item_id)
    if source is None:
        return None
    scale = icon_scale(item_id, radius)
    return source.width() * scale, source.height() * scale


def vertex_icon_bounds(radius: float) -> Optional[Tuple[float, float]]:
    item_id = vertex_icon()
    source = source_image(VERTEX, item_id)
    if source is None:
        return None
    scale = icon_scale(item_id, radius) + 1
    return source.width() * scale, source.height() * scale


def draw_vertex_icon(painter: QPainter, centre: QPointF, radius: float, fill: str) -> bool:
    item_id = vertex_icon()
    if source_image(VERTEX, item_id) is None:
        return False
    transform = painter.worldTransform()
    zoom = math.sqrt(abs(transform.determinant())) or 1.0
    pixmap = vertex_pixmap(item_id, QColor(fill).name(), icon_scale(item_id, radius * zoom))
    spot = transform.map(centre)
    painter.save()
    painter.resetTransform()
    painter.drawPixmap(QPointF(round(spot.x() - pixmap.width() / 2),
                               round(spot.y() - pixmap.height() / 2)), pixmap)
    painter.restore()
    return True


@lru_cache(maxsize=None)
def cursor_hotspots() -> dict:
    data = load_json(os.path.join(ASSET_DIR, CURSOR, "hotspots.json"), {})
    return data if isinstance(data, dict) else {}


def make_cursor(item_id: str, dpr: float = 1.0) -> Optional[QCursor]:
    source = source_image(CURSOR, item_id)
    if source is None:
        return None
    scale = max(1, round(CURSOR_TARGET_PX * dpr / max(source.width(), source.height())))
    pixmap = _scaled(source, scale)
    pixmap.setDevicePixelRatio(dpr)
    spot = cursor_hotspots().get(item_id, [0, 0])
    return QCursor(pixmap, int((spot[0] + 0.5) * scale / dpr), int((spot[1] + 0.5) * scale / dpr))


def current_cursor() -> str:
    return _state["cursor"]


def apply_cursor(item_id: str):
    app = QGuiApplication.instance()
    if app is None:
        return
    screen = app.primaryScreen()
    cursor = None if item_id == DEFAULT else make_cursor(
        item_id, screen.devicePixelRatio() if screen is not None else 1.0)
    if _state["override"]:
        app.restoreOverrideCursor()
        _state["override"] = False
    _state["cursor"] = DEFAULT
    if cursor is not None:
        app.setOverrideCursor(cursor)
        _state["override"] = True
        _state["cursor"] = item_id


def apply_wallet(wallet: Wallet):
    set_vertex_icon(wallet.equipped[VERTEX])
    apply_cursor(wallet.equipped[CURSOR])


def preview_pixmap(kind: str, item_id: str, box: int, fill: str) -> Optional[QPixmap]:
    source = source_image(kind, item_id)
    if source is None:
        return None
    scale = max(1, box // max(source.width(), source.height()))
    if kind == VERTEX:
        return vertex_pixmap(item_id, QColor(fill).name(), scale)
    return _scaled(source, scale)
