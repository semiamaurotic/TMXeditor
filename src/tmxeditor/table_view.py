"""Custom QTableView and delegate for the alignment grid.

Provides:
  - Inline cursor positioning inside cells (read-only by default)
  - Cmd+Enter to split at cursor position
  - F2 to enter edit mode (writable)
  - Visual emphasis for the active row/column
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QTimer
from PySide6.QtGui import QTextOption, QTextDocument, QPen, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPlainTextEdit,
    QStyle,
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

    TODO: Add native macOS context menu items (Translate, Look Up,
    Services) via PyObjC or custom actions — see conversation notes.
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
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
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

    def _wrap_mode(self):
        """Return the active QTextOption wrap mode based on config.

        When 'word_wrap' is True (default): WrapAtWordBoundaryOrAnywhere
          — wraps at spaces for English, falls back to character breaks
            for Thai/CJK (no spaces).
        When False: WrapAtWordBoundary
          — wraps only at spaces/word boundaries. Thai text without
            spaces will extend beyond the cell width.
        """
        from tmxeditor import config
        if config.get_display("word_wrap", True):
            return QTextOption.WrapAtWordBoundaryOrAnywhere
        return QTextOption.WordWrap

    def sizeHint(self, option, index):
        """Calculate cell height using QTextDocument for proper text wrapping."""
        text = index.data(Qt.DisplayRole) or ""
        if not text:
            return QSize(option.rect.width(), self._MIN_ROW_HEIGHT)

        font = option.font
        font.setPointSize(self._font_size_for_col(index.column()))

        doc = QTextDocument()
        doc.setDefaultFont(font)
        text_option = QTextOption()
        text_option.setWrapMode(self._wrap_mode())
        doc.setDefaultTextOption(text_option)
        doc.setPlainText(text)

        # Use available column width (minus padding)
        width = option.rect.width() if option.rect.width() > 0 else 300
        doc.setTextWidth(max(width - 16, 50))  # 16px for padding (8px each side)

        height = int(doc.size().height()) + 12  # 12px for top/bottom padding
        return QSize(width, max(height, self._MIN_ROW_HEIGHT))

    def paint(self, painter, option, index):
        """Paint cell text with proper word wrapping for Thai/CJK."""
        # Let the default style draw selection/focus/background
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            # Draw background and focus rect, but NOT the text
            option.text = ""
            style.drawControl(style.ControlElement.CE_ItemViewItem, option, painter, option.widget)

        # Draw subtle horizontal separator at bottom of cell
        painter.save()
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        y = option.rect.bottom()
        painter.drawLine(option.rect.left(), y, option.rect.right(), y)
        painter.restore()

        text = index.data(Qt.DisplayRole) or ""
        if not text:
            return

        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        text_option = QTextOption()
        text_option.setWrapMode(self._wrap_mode())
        doc.setDefaultTextOption(text_option)
        doc.setPlainText(text)
        doc.setTextWidth(max(option.rect.width() - 16, 50))

        # Use white text when selected so it's readable on the highlight
        if option.state & QStyle.StateFlag.State_Selected:
            palette = option.palette
            color = palette.color(palette.ColorGroup.Active, palette.ColorRole.HighlightedText)
            doc.setDefaultStyleSheet(f"body {{ color: {color.name()}; }}")
            doc.setHtml(f"<body>{doc.toPlainText()}</body>")

        painter.save()
        painter.translate(option.rect.left() + 8, option.rect.top() + 6)
        doc.drawContents(painter)
        painter.restore()

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

        # Column sizing — col 0 interactive, col 1 stretches to fill
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Interactive)

        # Apply word wrap from config
        self._apply_word_wrap()

        # Vertical header (row numbers)
        vheader = self.verticalHeader()
        vheader.setDefaultSectionSize(44)
        vheader.setSectionResizeMode(QHeaderView.ResizeToContents)

        # Reflow row heights when column is resized
        header.sectionResized.connect(self._on_column_resized)

        # Disable built-in grid (we draw horizontal lines in the delegate)
        self.setShowGrid(False)

    # ── Word wrap & column sizing helpers ───────────────────────

    def _apply_word_wrap(self) -> None:
        """Apply the word wrap setting from config."""
        from tmxeditor import config
        wrap = config.get_display("word_wrap", True)
        self.setWordWrap(wrap)
        # Reflow row heights immediately (user toggled setting)
        self._reflow_rows()

    def _reflow_rows(self) -> None:
        """Force recalculation of all visible row heights."""
        vheader = self.verticalHeader()
        vheader.setSectionResizeMode(QHeaderView.ResizeToContents)

    def _freeze_row_heights(self) -> None:
        """Lock row heights to current values during resize for performance."""
        vheader = self.verticalHeader()
        if vheader.sectionResizeMode(0) != QHeaderView.Fixed:
            vheader.setSectionResizeMode(QHeaderView.Fixed)

    def _schedule_reflow(self) -> None:
        """Debounced reflow — freezes rows during resize, recalculates when stable."""
        self._freeze_row_heights()
        if not hasattr(self, "_reflow_timer"):
            self._reflow_timer = QTimer(self)
            self._reflow_timer.setSingleShot(True)
            self._reflow_timer.setInterval(150)
            self._reflow_timer.timeout.connect(self._reflow_rows)
        self._reflow_timer.start()

    def _on_column_resized(self, _logical_index: int, _old_size: int, _new_size: int) -> None:
        """Reflow row heights when user drags the column divider."""
        self._schedule_reflow()

    def resizeEvent(self, event) -> None:
        """On window resize, apply column ratio and schedule deferred reflow."""
        super().resizeEvent(event)
        from tmxeditor import config
        header = self.horizontalHeader()
        total = self.viewport().width()
        if total > 0 and self.model() and self.model().columnCount() >= 2:
            ratio = config.get_display("column_ratio", 0.5)
            col0_width = int(total * ratio)
            header.resizeSection(0, col0_width)
        self._schedule_reflow()

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
