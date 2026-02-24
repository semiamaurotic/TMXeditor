"""Entry point for TMX Alignment Editor."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEvent
    from tmxeditor.main_window import MainWindow

    class TMXApplication(QApplication):
        def __init__(self, argv, window):
            super().__init__(argv)
            self.main_window = window

        def event(self, event: QEvent) -> bool:
            # Handle macOS "File Open" events (e.g., double-clicking in Finder)
            if event.type() == QEvent.Type.FileOpen:
                file_path = event.file()
                if file_path:
                    self.main_window.load_file(file_path)
                    self.main_window.raise_()
                    self.main_window.activateWindow()
                return True
            return super().event(event)

    # Initialize the MainWindow first so our application layer can reference it.
    # Note: QApplication must be instantiated before any QWidget.
    # We do a two-step initialization of the app object.
    
    # 1. Create a base QApplication just enough to init the Qt GUI system
    app = QApplication.instance()
    if app is None:
        # Standard sys.argv is passed, but we'll re-init shortly
        app = QApplication(sys.argv)
        app_created_here = True
    else:
        app_created_here = False
        
    app.setApplicationName("TMX Alignment Editor")
    app.setOrganizationName("TMXEditor")

    # Set app icon (dock / taskbar / window)
    icon_path = Path(__file__).parent / "resources" / "app_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # We need a custom Application to handle macOS FileOpen events natively
    # PySide6 allows replacing the current 'instance' object loop behavior
    # if it hasn't started yet, but a cleaner way is to simply intercept events on the app instance.
    
    window = MainWindow()
    
    # macOS: Install an event filter on the QApplication
    # This is a safer alternative to subclassing QApplication when testing/embedded
    class MacFileOpenFilter(QEvent):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.FileOpen:
                file_path = event.file()
                if file_path:
                    window.load_file(file_path)
                    window.raise_()
                    window.activateWindow()
                return True
            return False
            
    # Keep reference to avoid garbage collection
    mac_filter = type('Filter', (QEvent,), {'eventFilter': MacFileOpenFilter.eventFilter})()
    app.installEventFilter(mac_filter)

    # Windows / CLI: Check command line arguments
    if len(sys.argv) > 1:
        # sys.argv[0] is the script name, sys.argv[1] is the first arg
        target_file = Path(sys.argv[1])
        if target_file.exists() and target_file.is_file():
            window.load_file(str(target_file))

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
