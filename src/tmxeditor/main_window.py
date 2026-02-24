"""Main application window — wires model, view, undo stack, and dialogs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QTransform, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

from tmxeditor import config
from tmxeditor.dialogs import EditDialog, FindReplaceDialog, SettingsDialog, SplitDialog
from tmxeditor.models import AlignmentDocument
from tmxeditor.table_model import AlignmentTableModel
from tmxeditor.table_view import AlignmentTableView
from tmxeditor.tmx_io import parse_tmx, write_tmx
from tmxeditor.undo import (
    DeleteEmptyRowCommand,
    EditCellCommand,
    MergeCommand,
    MoveCellCommand,
    SplitCommand,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMX Alignment Editor")
        self.resize(1100, 700)

        # Core state
        self._doc: AlignmentDocument | None = None
        self._dirty = False
        self._undo_stack = QUndoStack(self)
        self._find_dialog: FindReplaceDialog | None = None

        # Table model & view
        self._model = AlignmentTableModel(self)
        self._view = AlignmentTableView(self)
        self._view.setModel(self._model)
        self.setCentralWidget(self._view)

        # Connect inline signals from the table view
        self._view.split_at_position.connect(self._on_inline_split)
        self._view.inline_edit_confirmed.connect(self._on_inline_edit)

        # Status bar
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        # Menus, toolbar, shortcuts
        self._build_menus()
        self._build_toolbar()

        # Track undo stack state for dirty flag
        self._undo_stack.cleanChanged.connect(self._on_clean_changed)
        # Refresh the view after any undo/redo operation
        self._undo_stack.indexChanged.connect(self._on_undo_redo)

        self._update_status()

    # ── Menu construction ───────────────────────────────────────

    def _sc(self, action_name: str) -> str:
        """Shortcut helper."""
        return config.get_shortcut(action_name)

    def _build_menus(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        self._act_open = file_menu.addAction("&Open…", self._file_open)
        self._act_open.setShortcut(QKeySequence(self._sc("file_open")))

        self._act_save = file_menu.addAction("&Save", self._file_save)
        self._act_save.setShortcut(QKeySequence(self._sc("file_save")))

        self._act_save_as = file_menu.addAction("Save &As…", self._file_save_as)
        self._act_save_as.setShortcut(QKeySequence(self._sc("file_save_as")))

        file_menu.addSeparator()
        self._act_quit = file_menu.addAction("&Quit", self.close)
        self._act_quit.setShortcut(QKeySequence(self._sc("file_quit")))

        # Edit
        edit_menu = mb.addMenu("&Edit")
        self._act_undo = self._undo_stack.createUndoAction(self, "&Undo")
        self._act_undo.setShortcut(QKeySequence(self._sc("edit_undo")))
        edit_menu.addAction(self._act_undo)

        self._act_redo = self._undo_stack.createRedoAction(self, "&Redo")
        self._act_redo.setShortcut(QKeySequence(self._sc("edit_redo")))
        edit_menu.addAction(self._act_redo)

        edit_menu.addSeparator()
        self._act_find = edit_menu.addAction("&Find / Replace…", self._show_find)
        self._act_find.setShortcut(QKeySequence(self._sc("edit_find")))

        # Operations
        ops_menu = mb.addMenu("&Operations")

        self._act_split = ops_menu.addAction("Sp&lit Cell (dialog)", self._op_split_dialog)
        self._act_split.setShortcut(QKeySequence(self._sc("op_split")))

        self._act_merge = ops_menu.addAction("&Merge with Next", self._op_merge)
        self._act_merge.setShortcut(QKeySequence(self._sc("op_merge")))

        ops_menu.addSeparator()
        self._act_move_up = ops_menu.addAction("Move Cell &Up", self._op_move_up)
        self._act_move_up.setShortcut(QKeySequence(self._sc("op_move_up")))

        self._act_move_down = ops_menu.addAction("Move Cell &Down", self._op_move_down)
        self._act_move_down.setShortcut(QKeySequence(self._sc("op_move_down")))

        ops_menu.addSeparator()
        self._act_edit = ops_menu.addAction("&Edit Cell…", self._op_edit_cell)
        self._act_edit.setShortcut(QKeySequence(self._sc("op_edit_cell")))

        self._act_delete_empty = ops_menu.addAction("&Delete Empty Row", self._op_delete_empty_row)
        self._act_delete_empty.setShortcut(QKeySequence(self._sc("op_delete_empty_row")))

        # View
        view_menu = mb.addMenu("&View")

        self._act_word_wrap = view_menu.addAction("Allow Wrapping Within Words", self._toggle_word_wrap)
        self._act_word_wrap.setCheckable(True)
        self._act_word_wrap.setChecked(config.get_display("word_wrap", True))

        view_menu.addSeparator()
        self._act_font_up = view_menu.addAction("Increase Column Font", self._font_increase)
        self._act_font_up.setShortcut(QKeySequence("Ctrl+="))

        self._act_font_down = view_menu.addAction("Decrease Column Font", self._font_decrease)
        self._act_font_down.setShortcut(QKeySequence("Ctrl+-"))

        # Settings
        view_menu.addSeparator()
        self._act_settings = view_menu.addAction("&Settings…", self._show_settings)
        self._act_settings.setShortcut(QKeySequence("Ctrl+,"))

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(tb)
        self.setUnifiedTitleAndToolBarOnMac(True)

        # Use native SF Symbols (macOS) via QIcon.fromTheme (PySide6 6.7+)
        # Tuples: (action, sf_name, label, shortcut_key, rotation_degrees)
        icon_actions = [
            (self._act_open, "folder", "Open File", "file_open", 0),
            (self._act_save, "arrow.down.doc", "Save", "file_save", 0),
            (self._act_undo, "arrow.uturn.backward", "Undo", "edit_undo", 0),
            (self._act_redo, "arrow.uturn.forward", "Redo", "edit_redo", 0),
            (self._act_split, "square.and.line.vertical.and.square", "Split Cell", "op_split", 90),
            (self._act_merge, "arrow.triangle.merge", "Merge with Next", "op_merge", 180),
            (self._act_move_up, "arrow.up", "Move Cell Up", "op_move_up", 0),
            (self._act_move_down, "arrow.down", "Move Cell Down", "op_move_down", 0),
            (self._act_edit, "pencil", "Edit Cell", "op_edit_cell", 0),
            (self._act_delete_empty, "delete.left", "Delete Empty Row", "op_delete_empty_row", 0),
        ]
        for action, sf_name, label, sc_key, rotation in icon_actions:
            icon = QIcon.fromTheme(sf_name)
            if rotation:
                icon = self._rotated_icon(icon, rotation)
            action.setIcon(icon)
            shortcut = self._mac_shortcut(self._sc(sc_key))
            tip = f"{label} ({shortcut})" if shortcut else label
            action.setToolTip(tip)

        # Helper to create an expanding spacer
        def _spacer() -> QWidget:
            w = QWidget()
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            return w

        # Layout: Open+Save (left) | spacer | center group | spacer | Edit+Delete (right)
        tb.addAction(self._act_open)
        tb.addAction(self._act_save)
        tb.addWidget(_spacer())
        tb.addAction(self._act_undo)
        tb.addAction(self._act_redo)
        tb.addSeparator()
        tb.addAction(self._act_split)
        tb.addAction(self._act_merge)
        tb.addSeparator()
        tb.addAction(self._act_move_up)
        tb.addAction(self._act_move_down)
        tb.addWidget(_spacer())
        tb.addAction(self._act_edit)
        tb.addAction(self._act_delete_empty)

    @staticmethod
    def _rotated_icon(icon: QIcon, degrees: int) -> QIcon:
        """Return a rotated copy of the given icon."""
        # Render at 2x for Retina displays
        size = 32
        pixmap = icon.pixmap(size, size)
        transform = QTransform().rotate(degrees)
        rotated = pixmap.transformed(transform, Qt.SmoothTransformation)
        return QIcon(rotated)

    @staticmethod
    def _mac_shortcut(shortcut: str) -> str:
        """Convert a Qt shortcut string to Mac symbol notation."""
        if not shortcut:
            return ""
        result = shortcut
        result = result.replace("Ctrl+", "\u2318")
        result = result.replace("Alt+", "\u2325")
        result = result.replace("Shift+", "\u21E7")
        result = result.replace("Meta+", "\u2303")
        return result

    # ── Status bar ──────────────────────────────────────────────

    def _update_status(self) -> None:
        if self._doc is None:
            self._status.showMessage("No file loaded")
            return
        path = self._doc.file_path or "Untitled"
        rows = self._doc.row_count()
        langs = f"{self._doc.source_lang} → {self._doc.target_lang}"
        dirty_mark = " •" if self._dirty else ""
        row = self._view.current_row() + 1 if self._view.current_row() >= 0 else 0
        col_name = "Source" if self._view.current_col() == 0 else "Target"
        self._status.showMessage(
            f"{Path(path).name}{dirty_mark}  |  {rows} rows  |  {langs}  |  Row {row} · {col_name}"
        )

    def _on_clean_changed(self, clean: bool) -> None:
        self._dirty = not clean
        self._update_title()
        self._update_status()

    def _on_undo_redo(self, _idx: int) -> None:
        """Refresh the view after any undo/redo operation."""
        self._model.notify_data_changed()
        self._update_status()

    def _update_title(self) -> None:
        name = Path(self._doc.file_path).name if self._doc and self._doc.file_path else "Untitled"
        dirty = " \u2022" if self._dirty else ""
        self.setWindowTitle(f"{name}{dirty}")

    # ── File operations ─────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        """Return True if it's OK to discard unsaved changes."""
        if not self._dirty:
            return True
        ans = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return ans == QMessageBox.Discard

    def _file_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open TMX", "", "TMX files (*.tmx);;All files (*)"
        )
        if not path:
            return
        self.load_file(path)

    def load_file(self, path: str | Path) -> bool:
        """Load a TMX file and return True on success. Can be called externally."""
        try:
            doc = parse_tmx(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open file:\n{exc}")
            return False
            
        self._doc = doc
        self._model.set_document(doc)
        self._undo_stack.clear()
        self._undo_stack.setClean()
        self._dirty = False
        self._update_title()
        self._update_status()
        if doc.row_count() > 0:
            self._view.select_cell(0, 0)
        return True

    def _file_save(self) -> None:
        if self._doc is None:
            return
        if self._doc.file_path is None:
            self._file_save_as()
            return
        self._do_save(self._doc.file_path)

    def _file_save_as(self) -> None:
        if self._doc is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save TMX As", "", "TMX files (*.tmx);;All files (*)"
        )
        if not path:
            return
        self._doc.file_path = path
        self._do_save(path)

    def _do_save(self, path: str) -> None:
        try:
            write_tmx(self._doc, path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._undo_stack.setClean()
        self._dirty = False
        self._update_title()
        self._update_status()

    # ── Inline signals from table view ──────────────────────────

    def _on_inline_split(self, row: int, col: int, pos: int) -> None:
        """Called when user presses Cmd+Enter inside a cell."""
        if self._doc is None:
            return
        text = self._doc.get_cell(row, col)
        if not text or pos <= 0 or pos >= len(text):
            return
        cmd = SplitCommand(self._doc, row, col, pos)
        self._push_cmd(cmd)
        # Select the cell that received the right part of the split
        self._view.select_cell(row + 1, col)

    def _on_inline_edit(self, row: int, col: int, old_text: str, new_text: str) -> None:
        """Called when user confirms an inline text edit (F2 → type → Enter)."""
        if self._doc is None:
            return
        cmd = EditCellCommand(self._doc, row, col, old_text, new_text)
        self._push_cmd(cmd)

    # ── Alignment operations ────────────────────────────────────

    def _require_doc_and_row(self) -> bool:
        if self._doc is None:
            return False
        if self._view.current_row() < 0:
            return False
        return True

    def _push_cmd(self, cmd) -> None:
        """Push an undo command, then refresh the view."""
        self._undo_stack.push(cmd)
        self._model.notify_data_changed()
        self._update_status()

    def _op_split_dialog(self) -> None:
        """Split via dialog (for users who prefer the modal approach)."""
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        col = self._view.current_col()
        text = self._doc.get_cell(row, col)
        if not text:
            QMessageBox.information(self, "Split", "Cell is empty — nothing to split.")
            return

        dlg = SplitDialog(text, parent=self)
        if dlg.exec() != SplitDialog.Accepted:
            return
        pos = dlg.split_position
        if pos is None:
            return
        cmd = SplitCommand(self._doc, row, col, pos)
        self._push_cmd(cmd)
        self._view.select_cell(row + 1, col)

    def _op_merge(self) -> None:
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        col = self._view.current_col()
        if row + 1 >= self._doc.row_count():
            QMessageBox.information(self, "Merge", "No row below to merge with.")
            return
        next_text = self._doc.get_cell(row + 1, col)
        cur_text = self._doc.get_cell(row, col)
        if not cur_text and not next_text:
            QMessageBox.information(self, "Merge", "Both cells are empty — nothing to merge.")
            return
        cmd = MergeCommand(self._doc, row, col)
        self._push_cmd(cmd)
        self._view.select_cell(row, col)

    def _op_move_up(self) -> None:
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        if row == 0:
            return
        col = self._view.current_col()
        cmd = MoveCellCommand(self._doc, row, col, -1)
        self._push_cmd(cmd)
        self._view.select_cell(row - 1, col)

    def _op_move_down(self) -> None:
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        if row + 1 >= self._doc.row_count():
            return
        col = self._view.current_col()
        cmd = MoveCellCommand(self._doc, row, col, +1)
        self._push_cmd(cmd)
        self._view.select_cell(row + 1, col)

    def _op_edit_cell(self) -> None:
        """Open modal edit dialog for text modification."""
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        col = self._view.current_col()
        old_text = self._doc.get_cell(row, col)
        col_name = "Source" if col == 0 else "Target"
        dlg = EditDialog(old_text, title=f"Edit {col_name} — Row {row + 1}", parent=self)
        if dlg.exec() != EditDialog.Accepted:
            return
        new_text = dlg.result_text
        if new_text is None or new_text == old_text:
            return
        cmd = EditCellCommand(self._doc, row, col, old_text, new_text)
        self._push_cmd(cmd)

    def _op_delete_empty_row(self) -> None:
        """Delete current row if both cells are blank."""
        if not self._require_doc_and_row():
            return
        row = self._view.current_row()
        col = self._view.current_col()
        src = self._doc.get_cell(row, 0)
        tgt = self._doc.get_cell(row, 1)
        if src or tgt:
            QMessageBox.information(
                self, "Delete Row",
                "Row is not empty. Both source and target must be blank to delete."
            )
            return
        cmd = DeleteEmptyRowCommand(self._doc, row)
        self._push_cmd(cmd)
        # Select the row that took this position (or last row)
        new_row = min(row, self._doc.row_count() - 1)
        if new_row >= 0:
            self._view.select_cell(new_row, col)

    # ── Find / Replace ──────────────────────────────────────────

    def _show_find(self) -> None:
        if self._find_dialog is None:
            self._find_dialog = FindReplaceDialog(self)
            self._find_dialog.btn_next.clicked.connect(self._find_next)
            self._find_dialog.btn_prev.clicked.connect(self._find_prev)
            self._find_dialog.btn_replace.clicked.connect(self._replace_one)
            self._find_dialog.btn_replace_all.clicked.connect(self._replace_all)
        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.find_field.setFocus()

    def _find_match(self, text: str, query: str, case_sensitive: bool) -> int:
        if not case_sensitive:
            return text.lower().find(query.lower())
        return text.find(query)

    def _find_next(self) -> None:
        self._do_find(forward=True)

    def _find_prev(self) -> None:
        self._do_find(forward=False)

    def _do_find(self, forward: bool = True) -> None:
        if self._doc is None or self._find_dialog is None:
            return
        query = self._find_dialog.find_field.text()
        if not query:
            return
        case = self._find_dialog.case_sensitive.isChecked()
        start_row = max(self._view.current_row(), 0)
        start_col = self._view.current_col()
        n = self._doc.row_count()
        step = 1 if forward else -1
        col = start_col + step
        row = start_row
        if col > 1:
            col = 0
            row += step
        elif col < 0:
            col = 1
            row += step

        checked = 0
        while checked < n * 2:
            r = row % n
            if r < 0:
                r += n
            c = col % 2
            text = self._doc.get_cell(r, c)
            if self._find_match(text, query, case) >= 0:
                self._view.select_cell(r, c)
                self._update_status()
                return
            col += step
            if (forward and col > 1) or (not forward and col < 0):
                col = 0 if forward else 1
                row += step
            checked += 1

        QMessageBox.information(self, "Find", f"'{query}' not found.")

    def _replace_one(self) -> None:
        if self._doc is None or self._find_dialog is None:
            return
        query = self._find_dialog.find_field.text()
        replacement = self._find_dialog.replace_field.text()
        if not query:
            return
        row = self._view.current_row()
        col = self._view.current_col()
        if row < 0:
            return
        case = self._find_dialog.case_sensitive.isChecked()
        text = self._doc.get_cell(row, col)
        idx = self._find_match(text, query, case)
        if idx < 0:
            self._find_next()
            return
        new_text = text[:idx] + replacement + text[idx + len(query):]
        cmd = EditCellCommand(self._doc, row, col, text, new_text)
        self._push_cmd(cmd)
        self._find_next()

    def _replace_all(self) -> None:
        if self._doc is None or self._find_dialog is None:
            return
        query = self._find_dialog.find_field.text()
        replacement = self._find_dialog.replace_field.text()
        if not query:
            return
        case = self._find_dialog.case_sensitive.isChecked()
        count = 0
        # Group all replacements into a single undo step
        self._undo_stack.beginMacro("Replace All")
        for r in range(self._doc.row_count()):
            for c in range(2):
                text = self._doc.get_cell(r, c)
                if case:
                    if query in text:
                        new_text = text.replace(query, replacement)
                        cmd = EditCellCommand(self._doc, r, c, text, new_text)
                        self._undo_stack.push(cmd)
                        count += 1
                else:
                    lower_text = text.lower()
                    lower_query = query.lower()
                    if lower_query in lower_text:
                        new_text = text
                        idx = lower_text.find(lower_query)
                        while idx >= 0:
                            new_text = new_text[:idx] + replacement + new_text[idx + len(query):]
                            lower_text = new_text.lower()
                            idx = lower_text.find(lower_query, idx + len(replacement))
                        cmd = EditCellCommand(self._doc, r, c, text, new_text)
                        self._undo_stack.push(cmd)
                        count += 1
        self._undo_stack.endMacro()
        if count > 0:
            self._model.notify_data_changed()
            self._update_status()
        QMessageBox.information(
            self, "Replace All", f"Replaced in {count} cell(s)."
        )

    # ── Overrides ───────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:
        """Update status bar on navigation."""
        super().keyPressEvent(event)
        self._update_status()

    # ── Settings & Font Size ────────────────────────────────────

    def _show_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._apply_settings()

    def _apply_settings(self) -> None:
        """Re-apply settings after the Settings dialog changes them."""
        # Refresh the table to pick up new font sizes
        self._model.notify_data_changed()
        self._view._apply_word_wrap()
        self._view.viewport().update()
        self._update_status()
        # Note: shortcut changes require restart for menu accelerators
        # (the Settings dialog saves to disk; they take effect next launch)

    def _toggle_word_wrap(self) -> None:
        """Toggle word wrap on/off and persist the setting."""
        wrap = self._act_word_wrap.isChecked()
        config.set_display("word_wrap", wrap)
        config.save_settings()
        self._view._apply_word_wrap()
        self._model.notify_data_changed()

    def _font_increase(self) -> None:
        row = self._view.current_row()
        col = self._view.current_col()
        col_name = "source" if col == 0 else "target"
        current = config.get_font_size(col_name)
        config.set_font_size(col_name, current + 1)
        config.save_settings()
        self._model.notify_data_changed()
        self._view.select_cell(row, col)

    def _font_decrease(self) -> None:
        row = self._view.current_row()
        col = self._view.current_col()
        col_name = "source" if col == 0 else "target"
        current = config.get_font_size(col_name)
        config.set_font_size(col_name, current - 1)
        config.save_settings()
        self._model.notify_data_changed()
        self._view.select_cell(row, col)
