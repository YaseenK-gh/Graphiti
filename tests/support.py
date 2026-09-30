"""Shared test setup. Import this first in every test module (``from tests import support``).

Points the leaderboard/achievement files at a throwaway directory and runs Qt
headless, so tests never touch real player data or open windows.
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEST_DATA_DIR = tempfile.mkdtemp(prefix="graph_coloring_test_")
os.environ["GRAPH_COLORING_DATA_DIR"] = TEST_DATA_DIR

_app = None


def qapp():
    """The shared QApplication (created on first use)."""
    global _app
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    return _app
