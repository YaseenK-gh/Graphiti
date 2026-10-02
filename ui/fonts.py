import logging
import os

from PySide6.QtGui import QFont, QFontDatabase

from core.constants import PROJECT_ROOT

logger = logging.getLogger(__name__)

FONT_DIR = os.path.join(PROJECT_ROOT, "assets", "fonts")
FALLBACK = "Consolas"

PIXEL = "Press Start 2P"
BODY = "Minecraft Default"

_loaded = False


def _register(filename: str):
    path = os.path.join(FONT_DIR, filename)
    if not os.path.exists(path):
        return None
    font_id = QFontDatabase.addApplicationFont(path)
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    return families[0] if families else None


def load_fonts():
    global _loaded, PIXEL, BODY
    if _loaded:
        return
    _loaded = True
    PIXEL = _register("PressStart2P-Regular.ttf") or FALLBACK
    BODY = _register("mojangles-regular.ttf") or PIXEL
    if PIXEL == FALLBACK or BODY == FALLBACK:
        logger.warning("Bundled fonts missing; using %s", FALLBACK)
    QFont.insertSubstitution(BODY, PIXEL)


def _strategy(font: QFont, crisp: bool) -> QFont:
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias if crisp
                          else QFont.StyleStrategy.PreferAntialias)
    return font


def app_font() -> QFont:
    font = QFont(PIXEL)
    font.setPixelSize(12)
    return _strategy(font, True)


def pixel_font(px: int, crisp: bool = True) -> QFont:
    font = QFont(PIXEL)
    font.setPixelSize(px)
    return _strategy(font, crisp)


def body_font(px: int, crisp: bool = True) -> QFont:
    font = QFont(BODY)
    font.setPixelSize(px)
    font.setBold(False)
    return _strategy(font, crisp)
