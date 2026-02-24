"""Modal dialogs for cell editing, find/replace, split, and settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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
        self._editor.setReadOnly(False)  # writable so cursor blinks; _revert_text prevents actual changes
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


# ── Settings Dialog ────────────────────────────────────────────


class SettingsDialog(QDialog):
    """Settings pane with tabs for keyboard shortcuts and display.

    Shortcuts use QKeySequenceEdit so the user just presses the
    desired key combination — no special syntax needed.
    """

    def __init__(self, parent=None):
        from tmxeditor import config  # deferred to avoid circular import

        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(550, 480)

        self._config = config
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Tab 1: Keyboard Shortcuts ───────────────────
        shortcuts_tab = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_tab)

        hint = QLabel(
            "Click a shortcut field, then press the key combination you want."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; margin-bottom: 8px;")
        shortcuts_layout.addWidget(hint)

        # Scrollable area for the shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        form = QFormLayout(scroll_widget)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._shortcut_edits: dict[str, QKeySequenceEdit] = {}
        current_shortcuts = config.get_shortcuts()

        for action_id, label in config.ACTION_LABELS.items():
            edit = QKeySequenceEdit()
            current = current_shortcuts.get(action_id, "")
            if current:
                edit.setKeySequence(QKeySequence(current))
            self._shortcut_edits[action_id] = edit
            form.addRow(label + ":", edit)

        scroll.setWidget(scroll_widget)
        shortcuts_layout.addWidget(scroll)

        # Reset to defaults button
        reset_btn = QPushButton("Reset All to Defaults")
        reset_btn.clicked.connect(self._reset_shortcuts)
        shortcuts_layout.addWidget(reset_btn, alignment=Qt.AlignLeft)

        tabs.addTab(shortcuts_tab, "Keyboard Shortcuts")

        # ── Tab 2: Display ──────────────────────────────
        display_tab = QWidget()
        display_layout = QVBoxLayout(display_tab)

        font_group = QGroupBox("Column Font Sizes")
        font_form = QFormLayout(font_group)

        self._source_font_spin = QSpinBox()
        self._source_font_spin.setRange(config.MIN_FONT_SIZE, config.MAX_FONT_SIZE)
        self._source_font_spin.setValue(config.get_font_size("source"))
        self._source_font_spin.setSuffix(" pt")
        font_form.addRow("Source column:", self._source_font_spin)

        self._target_font_spin = QSpinBox()
        self._target_font_spin.setRange(config.MIN_FONT_SIZE, config.MAX_FONT_SIZE)
        self._target_font_spin.setValue(config.get_font_size("target"))
        self._target_font_spin.setSuffix(" pt")
        font_form.addRow("Target column:", self._target_font_spin)

        display_layout.addWidget(font_group)
        display_layout.addStretch()

        tabs.addTab(display_tab, "Display")

        # ── OK / Cancel ─────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _reset_shortcuts(self) -> None:
        """Reset all shortcut fields to built-in defaults."""
        defaults = self._config._load_defaults()
        for action_id, edit in self._shortcut_edits.items():
            default_seq = defaults.get(action_id, "")
            if default_seq:
                edit.setKeySequence(QKeySequence(default_seq))
            else:
                edit.clear()

    def _accept(self) -> None:
        # Collect shortcuts
        new_shortcuts = {}
        for action_id, edit in self._shortcut_edits.items():
            seq = edit.keySequence()
            new_shortcuts[action_id] = seq.toString() if not seq.isEmpty() else ""

        self._config.set_shortcuts(new_shortcuts)

        # Collect font sizes
        self._config.set_font_size("source", self._source_font_spin.value())
        self._config.set_font_size("target", self._target_font_spin.value())

        # Persist to disk
        self._config.save_settings()

        self.accept()
