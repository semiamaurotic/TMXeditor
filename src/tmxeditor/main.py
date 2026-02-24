"""Entry point for TMX Alignment Editor."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from tmxeditor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("TMX Alignment Editor")
    app.setOrganizationName("TMXEditor")

    # Set app icon (dock / taskbar / window)
    icon_path = Path(__file__).parent / "resources" / "app_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
