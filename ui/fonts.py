"""Bundled pixel fonts (both SIL Open Font License, see assets/fonts)."""

import logging
import os

from PySide6.QtGui import QFont, QFontDatabase

from core.constants import PROJECT_ROOT

logger = logging.getLogger(__name__)

FONT_DIR = os.path.join(PROJECT_ROOT, "assets", "fonts")
FALLBACK = "Consolas"

# Press Start 2P: titles, buttons, labels, the timer. VT323: longer multi-line text.
PIXEL = "Press Start 2P"
TERMINAL = "VT323"

_loaded = False


def load_fonts():
    """Register the bundled fonts once per process (needs a QApplication)."""
    global _loaded, PIXEL, TERMINAL
    if _loaded:
        return
    _loaded = True
    for filename, attr in (("PressStart2P-Regular.ttf", "PIXEL"), ("VT323-Regular.ttf", "TERMINAL")):
        font_id = QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, filename))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            globals()[attr] = families[0]
        else:
            logger.warning("Could not load %s; falling back to %s", filename, FALLBACK)
            globals()[attr] = FALLBACK


def pixel_font(px: int) -> QFont:
    font = QFont(PIXEL)
    font.setPixelSize(px)
    return font


def terminal_font(px: int) -> QFont:
    font = QFont(TERMINAL)
    font.setPixelSize(px)
    return font
