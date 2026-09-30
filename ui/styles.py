"""App-wide stylesheet for the pixel Game Boy look.

Panels, buttons and cards paint themselves (ui/widgets/pixel.py); this sheet
covers text roles, inputs, tables, scrollbars and stock dialogs. Labels pick
their colors from the panel they sit in: `QFrame[tone="dark"]` or light.
"""

from core.constants import (UI_BG, UI_BORDER, UI_BUTTON, UI_DANGER_TEXT, UI_DARK_LINE, UI_FIELD,
                            UI_INK, UI_INNER, UI_LIME, UI_LIME_DIM, UI_BAD_ON_LIGHT,
                            UI_MUTED_ON_LIGHT)
from ui import fonts

# Font sizes (px). The reference mockup is drawn at half this scale.
SIZE_CAPTION = 10
SIZE_TEXT = 12
SIZE_BUTTON_SMALL = 12
SIZE_BUTTON = 14
SIZE_SUBTITLE = 14
SIZE_HEADING = 16
SIZE_TITLE = 20
SIZE_BODY = 22       # VT323 runs small, so its sizes are larger.
SIZE_TIMER = 40


def pixel_family() -> str:
    return f"'{fonts.PIXEL}', '{fonts.FALLBACK}', monospace"


def terminal_family() -> str:
    return f"'{fonts.TERMINAL}', '{fonts.FALLBACK}', monospace"


def get_stylesheet() -> str:
    pixel, terminal = pixel_family(), terminal_family()
    return f"""
    QWidget {{
        background: transparent;
        color: {UI_INK};
        font-family: {pixel};
        font-size: {SIZE_TEXT}px;
    }}
    QDialog, QMessageBox {{
        background: {UI_INK};
    }}
    QLabel {{ background: transparent; }}

    /* Light context (default) */
    QLabel[role="title"] {{ font-size: {SIZE_TITLE}px; color: {UI_INK}; }}
    QLabel[role="subtitle"] {{ font-size: {SIZE_SUBTITLE}px; color: {UI_BORDER}; }}
    QLabel[role="heading"] {{ font-size: {SIZE_HEADING}px; color: {UI_INK}; }}
    QLabel[role="muted"] {{ font-size: {SIZE_CAPTION}px; color: {UI_MUTED_ON_LIGHT}; }}
    QLabel[role="caption"] {{ font-size: {SIZE_CAPTION}px; color: {UI_BORDER}; }}
    QLabel[role="error"] {{ font-family: {terminal}; font-size: 20px; color: {UI_BAD_ON_LIGHT}; }}
    QLabel[role="body"] {{ font-family: {terminal}; font-size: {SIZE_BODY}px; color: {UI_BORDER}; }}
    QLabel[role="badge"] {{
        font-size: {SIZE_TEXT}px; color: {UI_LIME}; background: {UI_INK}; padding: 5px 12px;
    }}

    /* Dark context: dark panels and every dialog */
    QFrame[tone="dark"] QLabel, QDialog QLabel, QMessageBox QLabel {{ color: {UI_BG}; }}
    QFrame[tone="dark"] QLabel[role="title"], QDialog QLabel[role="title"],
    QFrame[tone="dark"] QLabel[role="heading"], QDialog QLabel[role="heading"] {{ color: {UI_LIME}; }}
    QFrame[tone="dark"] QLabel[role="subtitle"], QDialog QLabel[role="subtitle"] {{ color: {UI_LIME_DIM}; }}
    QFrame[tone="dark"] QLabel[role="muted"], QDialog QLabel[role="muted"],
    QFrame[tone="dark"] QLabel[role="caption"], QDialog QLabel[role="caption"] {{ color: {UI_INNER}; }}
    QFrame[tone="dark"] QLabel[role="error"], QDialog QLabel[role="error"] {{ color: {UI_DANGER_TEXT}; }}
    QFrame[tone="dark"] QLabel[role="body"], QDialog QLabel[role="body"] {{ color: {UI_LIME_DIM}; }}
    QFrame[tone="dark"] QLabel[role="badge"], QDialog QLabel[role="badge"] {{
        color: {UI_INK}; background: {UI_LIME};
    }}

    QLineEdit {{
        background: {UI_FIELD};
        color: {UI_INK};
        border: 3px solid {UI_BORDER};
        border-top: 5px solid {UI_BORDER};
        border-left: 5px solid {UI_BORDER};
        padding: 6px 10px;
        font-size: {SIZE_BUTTON}px;
        selection-background-color: {UI_INK};
        selection-color: {UI_LIME};
    }}
    QLineEdit:read-only {{ background: {UI_BUTTON}; }}

    /* Stock push buttons (message boxes); game buttons paint themselves. */
    QMessageBox QPushButton {{
        background: {UI_BUTTON}; color: {UI_INK}; border: 3px solid {UI_BORDER};
        padding: 8px 16px; min-width: 90px; font-size: {SIZE_BUTTON_SMALL}px;
    }}
    QMessageBox QPushButton:hover, QMessageBox QPushButton:focus {{
        background: {UI_LIME};
    }}

    QTableWidget {{
        background: transparent;
        border: none;
        gridline-color: transparent;
        color: {UI_BG};
        font-size: {SIZE_TEXT}px;
    }}
    QTableWidget::item {{ border-bottom: 1px solid {UI_DARK_LINE}; padding: 4px 6px; }}
    QHeaderView {{ background: transparent; }}
    QHeaderView::section {{
        background: transparent; color: {UI_LIME}; border: none;
        border-bottom: 2px solid {UI_INNER}; padding: 6px; font-size: {SIZE_TEXT}px;
    }}

    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: {UI_INK}; width: 12px; border: none; }}
    QScrollBar::handle:vertical {{ background: {UI_DARK_LINE}; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QToolTip {{
        background: {UI_FIELD}; color: {UI_INK}; border: 2px solid {UI_BORDER};
        padding: 4px; font-family: {terminal}; font-size: 18px;
    }}
    """
