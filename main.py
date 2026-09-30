"""Graph Coloring — Color Theorem. Run: python main.py"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Graph Coloring")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
