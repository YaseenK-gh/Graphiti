import logging
import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia*=false")
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.accessories import Wallet
from core.commands import run_command
from core.constants import FROZEN, ICON_PATH
from ui.console import TerminalCommands
from ui.main_window import MainWindow


def set_taskbar_identity():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Graphiti")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("Graphiti")
    app.setWindowIcon(QIcon(ICON_PATH))
    command = " ".join(sys.argv[1:])
    if command:
        message = run_command(command, Wallet())
        print(message, flush=True)
        if FROZEN:
            QMessageBox.information(None, "Graphiti", message)
    window = MainWindow()
    window.show()
    TerminalCommands(window).start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
