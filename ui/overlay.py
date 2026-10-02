from typing import Optional

from PySide6.QtCore import (QEasingCurve, QEvent, QEventLoop, QParallelAnimationGroup,
                            QVariantAnimation, Qt, Signal)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QPushButton, QVBoxLayout,
                               QWidget)

from core.constants import UI_INK
from ui.screens import make_button, make_label, make_panel, panel_layout
from ui.styles import GAP

ANIMATION_MS = 180
SLIDE_PX = 36


def overlay_host(widget: Optional[QWidget]) -> Optional[QWidget]:
    window = widget.window() if widget is not None else None
    return getattr(window, "overlay_host", None)


class Overlay(QWidget):
    finished = Signal(int)
    Accepted, Rejected = 1, 0

    def __init__(self, parent: Optional[QWidget] = None, width_fraction: float = 0.46,
                 min_width: int = 460, max_width: int = 720, max_height_fraction: float = 0.9):
        host = overlay_host(parent)
        super().__init__(host or parent)
        self.host = host
        self.width_fraction, self.min_width, self.max_width = width_fraction, min_width, max_width
        self.max_height_fraction = max_height_fraction
        self.result_ = self.Rejected
        self._loop: Optional[QEventLoop] = None
        self._anim: Optional[QParallelAnimationGroup] = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

        self.panel = make_panel(dark=True)
        self.layout_ = panel_layout(self.panel)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.panel)
        row.addStretch(1)
        self._outer.addLayout(row)
        self._outer.addStretch(1)
        if host is not None:
            host.installEventFilter(self)


    def _fit_to_host(self):
        area = self.host.rect() if self.host is not None else self.parentWidget().rect()
        self.setGeometry(area)
        width = max(self.min_width, min(self.max_width, int(area.width() * self.width_fraction)))
        self.panel.setFixedWidth(min(width, area.width() - 32))
        self.panel.setMaximumHeight(int(area.height() * self.max_height_fraction))

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == QEvent.Type.Resize and self.isVisible():
            self._fit_to_host()
        return False


    def open(self):
        if self.parentWidget() is None:
            self.show()
            return
        self._fit_to_host()
        self.show()
        self.raise_()
        self._animate_in()
        first = self._first_focus()
        (first or self).setFocus()

    def exec(self) -> int:
        self.open()
        self._loop = QEventLoop()
        self._loop.exec()
        self._loop = None
        return self.result_

    def _first_focus(self) -> Optional[QWidget]:
        for widget in self.panel.findChildren(QWidget):
            if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.isVisibleTo(self.panel) \
                    and widget.isEnabled():
                return widget
        return None

    def _animate_in(self):
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.0)
        self.setGraphicsEffect(effect)
        fade = QVariantAnimation(self)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.valueChanged.connect(effect.setOpacity)
        slide = QVariantAnimation(self)
        slide.setStartValue(SLIDE_PX)
        slide.setEndValue(0)
        slide.valueChanged.connect(lambda v: self._outer.setContentsMargins(0, 2 * int(v), 0, 0))
        group = QParallelAnimationGroup(self)
        for anim in (fade, slide):
            anim.setDuration(ANIMATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(anim)
        group.finished.connect(lambda: self.setGraphicsEffect(None))
        group.start()
        self._anim = group


    def done(self, result: int):
        self.result_ = result
        if self._anim is not None:
            self._anim.stop()
        self.hide()
        if self.host is not None:
            self.host.removeEventFilter(self)
        if self._loop is not None:
            self._loop.quit()
        self.finished.emit(result)
        self.deleteLater()

    def accept(self):
        self.done(self.Accepted)

    def reject(self):
        self.done(self.Rejected)


    def paintEvent(self, event):
        backdrop = QColor(UI_INK)
        backdrop.setAlpha(170)
        QPainter(self).fillRect(self.rect(), backdrop)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.reject()
        event.accept()

    def wheelEvent(self, event):
        event.accept()


class ConfirmOverlay(Overlay):
    def __init__(self, parent: QWidget, title: str, message: str, yes: str = "YES", no: str = "NO",
                 danger: bool = False):
        super().__init__(parent, width_fraction=0.44, min_width=560, max_width=680)
        self.layout_.addWidget(make_label(title.upper(), role="title", wrap=True))
        self.layout_.addWidget(make_label(message, role="body", wrap=True))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        self.no_btn = make_button(no, self.reject, variant="dark")
        self.yes_btn = make_button(yes, self.accept, variant="danger" if danger else "light")
        buttons.addWidget(self.no_btn)
        buttons.addWidget(self.yes_btn)
        self.layout_.addSpacing(4)
        self.layout_.addLayout(buttons)

    def _first_focus(self) -> QPushButton:
        return self.no_btn


def confirm(parent: QWidget, title: str, message: str, yes: str = "YES", no: str = "NO",
            danger: bool = False) -> bool:
    return ConfirmOverlay(parent, title, message, yes, no, danger).exec() == Overlay.Accepted
