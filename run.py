import logging
import sys

import qdarktheme
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from odbot.main_window import MainWindow
from odbot.utils import resource_path

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def main():
    app = QApplication()

    # Set application name and version
    app.setApplicationName("MindstormsDashboard")
    app.setApplicationVersion("0.1.0")

    # Set application icon
    app.setWindowIcon(QIcon(resource_path("odbot/assets/icon.png")))

    # Set dark theme
    qdarktheme.setup_theme("auto", custom_colors={"[dark]": {
        "background": "#282c34",
        "primary": "#c0bdbd",}})

    # Create main window
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
