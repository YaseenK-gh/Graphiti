from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.constants import UI_DANGER_TEXT, UI_LIME, UI_LIME_DIM
from ui.styles import GAP_TIGHT

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
STYLE = "color: {};"


class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP_TIGHT)
        first = QHBoxLayout()
        first.setSpacing(GAP_TIGHT)
        self.score_label = self._label()
        self.conflict_label = self._label()
        first.addWidget(self.score_label)
        first.addWidget(self._label("|"))
        first.addWidget(self.conflict_label)
        first.addStretch()
        layout.addLayout(first)
        self.colored_label = self._label()
        layout.addWidget(self.colored_label)
        self.colors_label = self._label()
        layout.addWidget(self.colors_label)
        self.set_conflicts(0)

    @staticmethod
    def _label(text: str = "") -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "caption")
        label.setAlignment(LEFT)
        label.setStyleSheet(STYLE.format(UI_LIME_DIM))
        return label

    def set_score(self, text: str):
        self.score_label.setText(text)

    def set_conflicts(self, count: int):
        if count:
            self.conflict_label.setText(f"{count} CONFLICT{'S' if count != 1 else ''}")
            self.conflict_label.setStyleSheet(STYLE.format(UI_DANGER_TEXT))
        else:
            self.conflict_label.setText("NO CONFLICTS")
            self.conflict_label.setStyleSheet(STYLE.format(UI_LIME_DIM))

    def set_progress(self, colored: int, total: int, target: int):
        self.colored_label.setText(f"COLORED: {colored}/{total} | TARGET: {target} COLORS")

    def set_colors(self, used: int, target: int):
        good = 0 < used <= target
        self.colors_label.setText(f"COLORS USED: {used}")
        self.colors_label.setStyleSheet(STYLE.format(UI_LIME if good else UI_LIME_DIM))
