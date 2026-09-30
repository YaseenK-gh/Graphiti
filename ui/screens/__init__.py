"""Screen base class and small layout helpers shared by every screen."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from core.constants import UI_INNER
from ui.widgets.pixel import Divider, PixelButton, PixelPanel


class BaseScreen(QWidget):
    """Base class for all game screens."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.game_state = main_window.game_state

    def on_show(self):
        """Called when the screen becomes visible. Override in subclasses."""

    def on_hide(self):
        """Called when another screen replaces this one. Override in subclasses."""


def make_label(text: str = "", role: Optional[str] = None, wrap: bool = False,
               align=Qt.AlignmentFlag.AlignCenter) -> QLabel:
    """Roles: title, subtitle, heading, muted, caption, error, body (terminal font), badge."""
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    label.setAlignment(align)
    label.setWordWrap(wrap)
    if role == "title":
        shadow = QGraphicsDropShadowEffect(label)
        shadow.setBlurRadius(0)
        shadow.setOffset(3, 3)
        shadow.setColor(QColor(UI_INNER))
        label.setGraphicsEffect(shadow)
    return label


def make_button(text: str, slot=None, width: Optional[int] = None, height: Optional[int] = None,
                variant: str = "light", small: bool = False) -> PixelButton:
    """variant: light, dark, danger or tab."""
    button = PixelButton(text, variant=variant, small=small)
    if width:
        button.setFixedWidth(width)
    button.setFixedHeight(height or button.sizeHint().height())
    if slot is not None:
        button.clicked.connect(slot)
    return button


def make_panel(dark: bool = False) -> PixelPanel:
    return PixelPanel("dark" if dark else "light")


def make_divider(dark: bool = False) -> Divider:
    return Divider(dark)


def set_text_color(label: QLabel, color: Optional[str]):
    """Override a label's role color (None restores it)."""
    label.setStyleSheet(f"color: {color};" if color else "")
