"""Vertex-count (n) input with live validation, shared by PRE_GAME and FREE_GRAPH_SELECT."""

from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QMessageBox, QVBoxLayout, QWidget

from core.constants import GRAPH_CONSTRAINTS
from core.graph_manager import GraphManager
from core.validation import validate_n


class NInput(QWidget):
    """Emits `validity_changed(bool)` as the player types and `submitted()` on Enter when valid."""

    validity_changed = Signal(bool)
    submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_graph_type: Optional[str] = None
        self.prev_n: Optional[int] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.range_label = QLabel()
        self.range_label.setProperty("role", "caption")
        self.range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.range_label)
        self.n_input = QLineEdit()
        self.n_input.setFixedWidth(180)
        self.n_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.n_input.setMaxLength(8)
        self.n_input.textChanged.connect(self.on_n_changed)
        self.n_input.returnPressed.connect(self._on_return)
        layout.addWidget(self.n_input, alignment=Qt.AlignmentFlag.AlignCenter)
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setProperty("role", "error")
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(28)
        layout.addWidget(self.error_label)
        self.is_valid = False

    def set_graph_type(self, graph_type: Optional[str], default_n: Optional[int] = None,
                       prev_n: Optional[int] = None):
        """prev_n: n of the previous level of this type; n must exceed it (locked once it's the max)."""
        self.selected_graph_type = graph_type
        self.prev_n = prev_n
        locked = False
        if graph_type in GRAPH_CONSTRAINTS:
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            locked = prev_n is not None and prev_n >= hi
            if prev_n is not None:
                lo = min(prev_n + 1, hi)
            self.range_label.setText(f"NUMBER OF VERTICES n  ({hi})" if locked
                                     else f"NUMBER OF VERTICES n  ({lo}–{hi})")
            if default_n is None:
                default_n = lo if prev_n is not None else GraphManager.default_n(graph_type)
            self.n_input.setText(str(default_n))
        else:
            self.range_label.setText("NUMBER OF VERTICES n")
        self.n_input.setReadOnly(locked)
        self.on_n_changed(self.n_input.text())

    def validate_and_get_n(self, text: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
        """Validate n input. Returns (n or None, error message or None)."""
        return validate_n(self.n_input.text() if text is None else text, self.selected_graph_type,
                          self.prev_n)

    def on_n_changed(self, text: str):
        """Live validation as the player types."""
        _n, error = self.validate_and_get_n(text)
        self.error_label.setText(error or "")
        self.is_valid = error is None
        self.validity_changed.emit(self.is_valid)

    def _on_return(self):
        if self.is_valid:
            self.submitted.emit()

    def focus(self):
        self.n_input.setFocus()
        self.n_input.selectAll()


def show_error_with_retry(parent: QWidget, n_input: NInput, title: str, message: str,
                          current_n: Optional[int] = None):
    """Error dialog offering to retry with a smaller n."""
    graph_type = n_input.selected_graph_type
    suggested_n = None
    msg = f"{message}\n"
    if current_n is not None and graph_type in GRAPH_CONSTRAINTS:
        suggested_n = GraphManager.suggested_lower_n(graph_type, current_n)
        if n_input.prev_n is not None:
            suggested_n = max(suggested_n, min(n_input.prev_n + 1, GRAPH_CONSTRAINTS[graph_type][1]))
        msg += f"\nTry: n = {suggested_n}"
    reply = QMessageBox.warning(parent, title, msg,
                                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
    if reply == QMessageBox.StandardButton.Retry and suggested_n is not None:
        n_input.n_input.setText(str(suggested_n))
    n_input.focus()
