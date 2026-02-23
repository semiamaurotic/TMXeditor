"""Qt table model backed by an AlignmentDocument.

Uses QAbstractTableModel so that QTableView only requests data for
visible rows — essential for performance with large TMX files.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class AlignmentTableModel(QAbstractTableModel):
    """Two-column model: Source (col 0) and Target (col 1)."""

    COLUMNS = ("Source", "Target")

    def __init__(self, parent=None):
        super().__init__(parent)
        from tmxeditor.models import AlignmentDocument

        self._doc: AlignmentDocument | None = None

    # ── Public API ──────────────────────────────────────────────

    @property
    def document(self):
        return self._doc

    def set_document(self, doc):
        """Replace the underlying document and refresh the view."""
        self.beginResetModel()
        self._doc = doc
        self.endResetModel()

    def notify_data_changed(self) -> None:
        """Signal full refresh after structural edits (split/merge/move)."""
        self.beginResetModel()
        self.endResetModel()

    # ── QAbstractTableModel overrides ───────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._doc is None:
            return 0
        return self._doc.row_count()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 2

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or self._doc is None:
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return self._doc.get_cell(index.row(), index.column())
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal and 0 <= section < 2:
                label = self.COLUMNS[section]
                if self._doc:
                    lang = self._doc.source_lang if section == 0 else self._doc.target_lang
                    return f"{label} [{lang}]"
                return label
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        # Editable flag enables the inline cursor delegate
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
