import logging
import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia*=false")
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Graphiti")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
