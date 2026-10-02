import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="graph_coloring_test_")
os.environ["GRAPH_COLORING_DATA_DIR"] = TEST_DATA_DIR
os.environ["GRAPH_COLORING_NO_AUDIO"] = "1"

_app = None


def qapp():
    global _app
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    return _app
