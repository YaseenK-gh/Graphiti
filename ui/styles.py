from core.constants import (UI_BAD_ON_LIGHT, UI_BG, UI_BORDER, UI_BUTTON, UI_DANGER_TEXT,
                            UI_DARK_LINE, UI_FIELD, UI_INK, UI_INNER, UI_LIME, UI_LIME_DIM,
                            UI_MUTED_ON_LIGHT)
from ui import fonts

PIXEL_UNIT = 2
SIZE_BUTTON = 8 * PIXEL_UNIT
SIZE_BUTTON_SMALL = 8 * PIXEL_UNIT
SIZE_SUBTITLE = 8 * PIXEL_UNIT
SIZE_HEADING = 8 * PIXEL_UNIT
SIZE_TITLE = 12 * PIXEL_UNIT
SIZE_TIMER = 20 * PIXEL_UNIT
SIZE_DISPLAY = 24 * PIXEL_UNIT
SIZE_BODY = 12 * PIXEL_UNIT
LINE_GAP = 4 * PIXEL_UNIT


LINE_SPACING_CSS = f"line-height: {LINE_GAP}px; -qt-line-height-type: line-distance;"


def line_height_px(px: int) -> int:
    return px + LINE_GAP


def size_body() -> int:
    return SIZE_BODY


PAGE_MARGIN = 16
PANEL_MARGINS = (36, 28, 36, 28)
COMPACT_MARGINS = (22, 18, 22, 18)
GAP = 12
GAP_TIGHT = 8
GAP_SECTION = 20


def pixel_family() -> str:
    return f"'{fonts.PIXEL}', '{fonts.FALLBACK}', monospace"


def body_family() -> str:
    return f"'{fonts.BODY}', '{fonts.PIXEL}', '{fonts.FALLBACK}', monospace"


def get_stylesheet() -> str:
    pixel, body = pixel_family(), body_family()
    return f"""
    QWidget {{
        background: transparent;
        color: {UI_INK};
        font-family: {body};
        font-size: {SIZE_BODY}px;
        font-weight: normal;
    }}
    QLabel {{ background: transparent; padding-top: 2px; padding-bottom: 2px; }}

    QLabel[role="title"] {{ font-family: {pixel}; font-size: {SIZE_TITLE}px; color: {UI_INK}; }}
    QLabel[role="subtitle"] {{ font-family: {pixel}; font-size: {SIZE_SUBTITLE}px; color: {UI_BORDER}; }}
    QLabel[role="heading"] {{ font-family: {pixel}; font-size: {SIZE_HEADING}px; color: {UI_INK}; }}
    QLabel[role="muted"] {{ color: {UI_MUTED_ON_LIGHT}; }}
    QLabel[role="caption"] {{ color: {UI_BORDER}; }}
    QLabel[role="error"] {{ color: {UI_BAD_ON_LIGHT}; }}
    QLabel[role="body"] {{ color: {UI_BORDER}; }}
    QLabel[role="badge"] {{
        font-family: {pixel}; font-size: {SIZE_HEADING}px; color: {UI_LIME}; background: {UI_INK};
        padding: 8px 12px;
    }}
    QLabel[role="strip"] {{
        color: {UI_INK}; background: {UI_FIELD}; border: 3px solid {UI_BORDER}; padding: 4px 12px;
    }}

    QFrame[tone="dark"] QLabel {{ color: {UI_BG}; }}
    QFrame[tone="dark"] QLabel[role="title"],
    QFrame[tone="dark"] QLabel[role="heading"] {{ color: {UI_LIME}; }}
    QFrame[tone="dark"] QLabel[role="subtitle"] {{ color: {UI_LIME_DIM}; }}
    QFrame[tone="dark"] QLabel[role="muted"],
    QFrame[tone="dark"] QLabel[role="caption"] {{ color: {UI_INNER}; }}
    QFrame[tone="dark"] QLabel[role="error"] {{ color: {UI_DANGER_TEXT}; }}
    QFrame[tone="dark"] QLabel[role="body"] {{ color: {UI_LIME_DIM}; }}
    QFrame[tone="dark"] QLabel[role="badge"] {{ color: {UI_INK}; background: {UI_LIME}; }}

    QLineEdit {{
        background: {UI_FIELD};
        color: {UI_INK};
        border: 3px solid {UI_BORDER};
        border-top: 5px solid {UI_BORDER};
        border-left: 5px solid {UI_BORDER};
        padding: 6px 10px;
        font-family: {pixel};
        font-size: {SIZE_BUTTON}px;
        selection-background-color: {UI_INK};
        selection-color: {UI_LIME};
    }}
    QLineEdit:read-only {{ background: {UI_BUTTON}; }}

    QTableWidget {{
        background: transparent;
        border: none;
        gridline-color: transparent;
        color: {UI_BG};
    }}
    QTableWidget::item {{ border-bottom: 1px solid {UI_DARK_LINE}; padding: 4px 6px; }}
    QHeaderView {{ background: transparent; }}
    QHeaderView::section {{
        background: transparent; color: {UI_LIME}; border: none;
        border-bottom: 2px solid {UI_INNER}; padding: 6px;
    }}

    QSlider::groove:horizontal {{ background: {UI_DARK_LINE}; height: 10px; border: 2px solid {UI_BORDER}; }}
    QSlider::sub-page:horizontal {{ background: {UI_LIME}; border: 2px solid {UI_BORDER}; }}
    QSlider::handle:horizontal {{
        background: {UI_BUTTON}; border: 3px solid {UI_BORDER}; width: 16px; margin: -9px 0;
    }}
    QSlider::handle:horizontal:hover {{ background: {UI_LIME}; }}

    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: {UI_INK}; width: 12px; border: none; }}
    QScrollBar::handle:vertical {{ background: {UI_DARK_LINE}; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QToolTip {{
        background: {UI_FIELD}; color: {UI_INK}; border: 2px solid {UI_BORDER};
        padding: 4px;
    }}
    """
