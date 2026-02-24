"""Custom QTableView and delegate for the alignment grid.

Provides:
  - Inline cursor positioning inside cells (read-only by default)
  - Cmd+Enter to split at cursor position
  - F2 to enter edit mode (writable)
  - Visual emphasis for the active row/column
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPlainTextEdit,
    QStyledItemDelegate,
    QTableView,
    QWidget,
)


class _CellEditor(QPlainTextEdit):
    """In-cell editor that supports two modes:

    1. **Cursor mode** (default): user can position cursor and see a
       blinking caret, but text changes are reverted instantly.
       Cmd+Enter triggers a split at the cursor position.
    2. **Edit mode** (F2): user can modify text. Enter confirms,
       Escape cancels.

    We intentionally do NOT use setReadOnly() because macOS Qt
    completely hides the blinking caret in read-only widgets.
    Instead we keep the widget writable and revert any changes
    that happen outside edit mode.
    """

    split_at_cursor = Signal(int)  # emits cursor position
    edit_confirmed = Signal(str)  # emits new text
    edit_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._editable = False
        self._guard_text: str = ""  # text to revert to in cursor-only mode
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCursorWidth(2)
        self.setStyleSheet("QPlainTextEdit { padding: 4px; }")
        # Revert any text changes that happen in cursor-only mode
        self.textChanged.connect(self._on_text_changed)

    def set_guard_text(self, text: str) -> None:
        """Set the text that cursor-only mode reverts to."""
        self._guard_text = text

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        if editable:
            self.setStyleSheet(
                "QPlainTextEdit { padding: 4px; background-color: #fffbe6; }"
            )
        else:
            self.setStyleSheet("QPlainTextEdit { padding: 4px; }")
            # Snapshot current text as guard
            self._guard_text = self.toPlainText()

    def _on_text_changed(self) -> None:
        """In cursor-only mode, revert any text modifications."""
        if not self._editable and self.toPlainText() != self._guard_text:
            pos = self.textCursor().position()
            self.blockSignals(True)
            self.setPlainText(self._guard_text)
            cursor = self.textCursor()
            cursor.setPosition(min(pos, len(self._guard_text)))
            self.setTextCursor(cursor)
            self.blockSignals(False)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()

        # Cmd+Enter (macOS) or Ctrl+Enter → split at cursor
        if key in (Qt.Key_Return, Qt.Key_Enter) and (mods & Qt.ControlModifier):
            pos = self.textCursor().position()
            self.split_at_cursor.emit(pos)
            event.accept()
            return

        # F2 → toggle edit mode
        if key == Qt.Key_F2:
            if not self._editable:
                self.set_editable(True)
            event.accept()
            return

        # Escape → cancel
        if key == Qt.Key_Escape:
            self.edit_cancelled.emit()
            event.accept()
            return

        # In edit mode, Enter (without Cmd) confirms
        if self._editable and key in (Qt.Key_Return, Qt.Key_Enter) and not (mods & Qt.ControlModifier):
            self.edit_confirmed.emit(self.toPlainText())
            event.accept()
            return

        # Always pass to super — navigation keys work naturally,
        # and any text changes in cursor-only mode are reverted by _on_text_changed
        super().keyPressEvent(event)


class _InlineCursorDelegate(QStyledItemDelegate):
    """Delegate that creates inline cell editors for cursor positioning.
    
    Supports per-column font sizes via config.get_font_size().
    """

    _MIN_ROW_HEIGHT = 40

    split_requested = Signal(int, int, int)  # row, col, cursor_pos
    edit_confirmed = Signal(int, int, str, str)  # row, col, old_text, new_text

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_editor: _CellEditor | None = None
        self._current_index = None
        self._original_text = ""

    def _font_size_for_col(self, col: int) -> int:
        from tmxeditor import config
        return config.get_font_size("source" if col == 0 else "target")

    def createEditor(self, parent, option, index):
        editor = _CellEditor(parent)
        self._original_text = index.data(Qt.DisplayRole) or ""
        self._current_index = index
        self._current_editor = editor

        # Apply per-column font size
        font = editor.font()
        font.setPointSize(self._font_size_for_col(index.column()))
        editor.setFont(font)

        row = index.row()
        col = index.column()

        editor.split_at_cursor.connect(
            lambda pos: self.split_requested.emit(row, col, pos)
        )
        editor.edit_confirmed.connect(
            lambda new_text: self._on_edit_confirmed(row, col, new_text)
        )
        editor.edit_cancelled.connect(
            lambda: self._on_edit_cancelled(editor)
        )
        return editor

    def setEditorData(self, editor, index):
        text = index.data(Qt.DisplayRole) or ""
        self._original_text = text
        editor.blockSignals(True)
        editor.setPlainText(text)
        editor.set_guard_text(text)  # snapshot for cursor-only mode
        # Position cursor at end by default
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        # We handle commits ourselves via signals
        pass

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def initStyleOption(self, option, index):
        """Apply per-column font size in the painted (non-editing) cells."""
        super().initStyleOption(option, index)
        font = option.font
        font.setPointSize(self._font_size_for_col(index.column()))
        option.font = font

    def sizeHint(self, option, index):
        # Use per-column font size for size calculation
        option.font.setPointSize(self._font_size_for_col(index.column()))
        hint = super().sizeHint(option, index)
        if hint.height() < self._MIN_ROW_HEIGHT:
            hint.setHeight(self._MIN_ROW_HEIGHT)
        return hint

    def _on_edit_confirmed(self, row, col, new_text):
        if new_text != self._original_text:
            self.edit_confirmed.emit(row, col, self._original_text, new_text)
        if self._current_editor:
            self._current_editor.set_editable(False)
            # Close the editor
            self.commitData.emit(self._current_editor)
            self.closeEditor.emit(self._current_editor)

    def _on_edit_cancelled(self, editor):
        editor.setPlainText(self._original_text)
        editor.set_editable(False)
        self.closeEditor.emit(editor)


class AlignmentTableView(QTableView):
    """Two-column alignment grid with inline cursor positioning."""

    # Emitted when user presses Cmd+Enter to split
    split_at_position = Signal(int, int, int)  # row, col, cursor_pos
    # Emitted when user confirms an inline edit
    inline_edit_confirmed = Signal(int, int, str, str)  # row, col, old, new

    def __init__(self, parent=None):
        super().__init__(parent)

        # Appearance
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setSelectionBehavior(QTableView.SelectItems)

        # Open editor on single click or current change for cursor positioning
        self.setEditTriggers(
            QAbstractItemView.SelectedClicked
            | QAbstractItemView.DoubleClicked
        )

        # Custom inline delegate
        self._delegate = _InlineCursorDelegate(self)
        self._delegate.split_requested.connect(self.split_at_position.emit)
        self._delegate.edit_confirmed.connect(self.inline_edit_confirmed.emit)
        self.setItemDelegate(self._delegate)

        # Column sizing — stretch equally
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Vertical header (row numbers)
        vheader = self.verticalHeader()
        vheader.setDefaultSectionSize(44)
        vheader.setSectionResizeMode(QHeaderView.ResizeToContents)

        # Styling
        self.setStyleSheet(
            """
            QTableView {
                gridline-color: #d0d0d0;
                selection-background-color: #cce5ff;
                selection-color: #000;
            }
            QTableView::item {
                padding: 6px 8px;
            }
            QTableView::item:focus {
                border: 2px solid #0078d4;
            }
            QHeaderView::section {
                font-weight: bold;
                padding: 6px;
                background: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
            """
        )

    # ── Navigation helpers ──────────────────────────────────────

    def current_row(self) -> int:
        idx = self.currentIndex()
        return idx.row() if idx.isValid() else -1

    def current_col(self) -> int:
        idx = self.currentIndex()
        return idx.column() if idx.isValid() else 0

    def select_cell(self, row: int, col: int) -> None:
        """Move selection to a specific cell and restore focus."""
        model = self.model()
        if model is None:
            return
        if 0 <= row < model.rowCount() and 0 <= col < model.columnCount():
            idx = model.index(row, col)
            self.setCurrentIndex(idx)
            self.scrollTo(idx)
            # Ensure the table view has keyboard focus so arrow keys work
            self.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, event) -> None:
        """Enter/Return opens the inline cursor editor for splitting."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            idx = self.currentIndex()
            if idx.isValid() and self.state() != QAbstractItemView.EditingState:
                self.edit(idx)
                event.accept()
                return
        super().keyPressEvent(event)
