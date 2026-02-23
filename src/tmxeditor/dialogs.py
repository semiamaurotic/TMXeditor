"""Modal dialogs for cell editing, find/replace, and split positioning."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QCheckBox,
    QMessageBox,
)


# ── Edit Dialog ─────────────────────────────────────────────────


class EditDialog(QDialog):
    """Modal dialog for editing a segment's text.

    Returns the new text via ``result_text`` if accepted, or ``None``
    if cancelled.
    """

    def __init__(
        self,
        text: str,
        title: str = "Edit Segment",
        parent=None,
        *,
        cursor_position: int | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 300)
        self.result_text: str | None = None

        layout = QVBoxLayout(self)

        self._editor = QTextEdit()
        self._editor.setPlainText(text)
        self._editor.setAcceptRichText(False)
        layout.addWidget(self._editor)

        if cursor_position is not None:
            cursor = self._editor.textCursor()
            cursor.setPosition(min(cursor_position, len(text)))
            self._editor.setTextCursor(cursor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self.result_text = self._editor.toPlainText()
        self.accept()

    def cursor_position(self) -> int:
        """Return the current cursor position in the editor."""
        return self._editor.textCursor().position()


# ── Split Dialog ────────────────────────────────────────────────


class SplitDialog(QDialog):
    """Dialog that shows the segment text and lets the user position
    the cursor at the desired split point.

    Returns the cursor position via ``split_position`` if accepted.
    """

    def __init__(self, text: str, title: str = "Position cursor to split", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 250)
        self.split_position: int | None = None

        layout = QVBoxLayout(self)

        hint = QLabel("Place the cursor where you want to split, then press OK.")
        layout.addWidget(hint)

        self._editor = QTextEdit()
        self._editor.setPlainText(text)
        self._editor.setAcceptRichText(False)
        self._editor.setReadOnly(False)  # cursor can move but text can't change visually
        layout.addWidget(self._editor)

        # Prevent actual text changes (we only want cursor positioning)
        self._original_text = text
        self._editor.textChanged.connect(self._revert_text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _revert_text(self) -> None:
        """If the user types, revert to original text preserving cursor pos."""
        if self._editor.toPlainText() != self._original_text:
            pos = self._editor.textCursor().position()
            self._editor.blockSignals(True)
            self._editor.setPlainText(self._original_text)
            cursor = self._editor.textCursor()
            cursor.setPosition(min(pos, len(self._original_text)))
            self._editor.setTextCursor(cursor)
            self._editor.blockSignals(False)

    def _accept(self) -> None:
        self.split_position = self._editor.textCursor().position()
        if self.split_position == 0 or self.split_position >= len(self._original_text):
            QMessageBox.warning(
                self,
                "Invalid split position",
                "The cursor must be between the first and last character.",
            )
            return
        self.accept()


# ── Find / Replace Dialog ───────────────────────────────────────


class FindReplaceDialog(QDialog):
    """Non-modal find/replace dialog.

    Emits signals that the main window connects to for navigation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # Find row
        find_row = QHBoxLayout()
        find_row.addWidget(QLabel("Find:"))
        self.find_field = QLineEdit()
        find_row.addWidget(self.find_field)
        layout.addLayout(find_row)

        # Replace row
        replace_row = QHBoxLayout()
        replace_row.addWidget(QLabel("Replace:"))
        self.replace_field = QLineEdit()
        replace_row.addWidget(self.replace_field)
        layout.addLayout(replace_row)

        # Options
        self.case_sensitive = QCheckBox("Case sensitive")
        layout.addWidget(self.case_sensitive)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_next = QPushButton("Find Next")
        self.btn_prev = QPushButton("Find Previous")
        self.btn_replace = QPushButton("Replace")
        self.btn_replace_all = QPushButton("Replace All")
        btn_row.addWidget(self.btn_prev)
        btn_row.addWidget(self.btn_next)
        btn_row.addWidget(self.btn_replace)
        btn_row.addWidget(self.btn_replace_all)
        layout.addLayout(btn_row)

        # Close
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
