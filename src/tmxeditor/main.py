"""Entry point for TMX Alignment Editor."""

from __future__ import annotations

import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication
    from tmxeditor.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("TMX Alignment Editor")
    app.setOrganizationName("TMXEditor")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
