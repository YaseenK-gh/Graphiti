import html
from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from core.constants import UI_INNER
from ui.styles import COMPACT_MARGINS, GAP, LINE_SPACING_CSS, PANEL_MARGINS
from ui.widgets.pixel import Divider, PixelButton, PixelPanel


class BaseScreen(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.game_state = main_window.game_state
        self._fitted: List[Tuple[QWidget, float, int, int]] = []

    def fit(self, widget: QWidget, fraction: float, min_width: int, max_width: int) -> QWidget:
        self._fitted.append((widget, fraction, min_width, max_width))
        widget.setFixedWidth(min_width)
        return widget

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for widget, fraction, lo, hi in self._fitted:
            widget.setFixedWidth(max(lo, min(hi, int(self.width() * fraction))))

    def on_show(self):
        pass

    def on_hide(self):
        pass


class SpacedLabel(QLabel):
    def __init__(self, text: str = ""):
        super().__init__()
        self._plain = ""
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(text)

    def setText(self, text: str):
        self._plain = text
        self._render()

    def _render(self):
        if not self._plain:
            super().setText("")
            return
        body = html.escape(self._plain, quote=False).replace("\n", "<br>")
        super().setText(f'<div style="{LINE_SPACING_CSS}">{body}</div>')

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._render()

    def text(self) -> str:
        return self._plain


def make_label(text: str = "", role: Optional[str] = None, wrap: bool = False,
               align=Qt.AlignmentFlag.AlignCenter) -> QLabel:
    label = SpacedLabel(text) if wrap or role in ("body", "error") else QLabel(text)
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
                variant: str = "light", small: bool = False, icon: Optional[str] = None) -> PixelButton:
    button = PixelButton(text, variant=variant, small=small, icon=icon)
    if width:
        button.setFixedWidth(width)
    button.setFixedHeight(height or button.sizeHint().height())
    if slot is not None:
        button.clicked.connect(slot)
    return button


def make_panel(dark: bool = False) -> PixelPanel:
    return PixelPanel("dark" if dark else "light")


def panel_layout(panel: QWidget, compact: bool = False, spacing: int = GAP) -> QVBoxLayout:
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(*(COMPACT_MARGINS if compact else PANEL_MARGINS))
    layout.setSpacing(spacing)
    return layout


def make_divider(dark: bool = False) -> Divider:
    return Divider(dark)


def set_text_color(label: QLabel, color: Optional[str]):
    label.setStyleSheet(f"color: {color};" if color else "")
