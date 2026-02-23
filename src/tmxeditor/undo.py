"""Undo/Redo commands for alignment operations.

Each command is a QUndoCommand subclass that knows how to apply (redo)
and reverse (undo) a single atomic operation on an AlignmentDocument.
The commands do **not** touch the UI directly — they mutate the document
and the caller is responsible for signalling the table model to refresh.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from tmxeditor.models import AlignmentDocument, AlignmentRow


class SplitCommand(QUndoCommand):
    """Split a cell at a cursor position.

    *col*: 0 = source, 1 = target.
    After redo:
      - The active cell keeps text[:pos].
      - If the cell below in the same column is already blank, the right
        part fills that blank cell (no new row inserted).
      - Otherwise a new row is inserted at row+1 with text[pos:] in the
        active col and blank in the other col.
    """

    def __init__(
        self,
        doc: AlignmentDocument,
        row: int,
        col: int,
        pos: int,
        *,
        description: str = "Split",
    ) -> None:
        super().__init__(description)
        self._doc = doc
        self._row = row
        self._col = col
        self._pos = pos
        self._original_text: str = doc.get_cell(row, col)
        self._filled_existing: bool = False  # True if we filled a blank below
        self._new_row: AlignmentRow | None = None

    def redo(self) -> None:
        from tmxeditor.models import AlignmentRow

        left = self._original_text[: self._pos]
        right = self._original_text[self._pos :]

        # Strip a single leading space from the right part to avoid
        # double-spacing after a split at a word boundary.
        if right.startswith(" "):
            right = right[1:]

        self._doc.set_cell(self._row, self._col, left)

        # Check if the cell below in the same column is blank
        next_row = self._row + 1
        if next_row < self._doc.row_count():
            below_text = self._doc.get_cell(next_row, self._col)
            if not below_text:
                # Fill the existing blank cell
                self._filled_existing = True
                self._doc.set_cell(next_row, self._col, right)
                return

        # Otherwise insert a new row
        self._filled_existing = False
        if self._col == 0:
            new_row = AlignmentRow(source=right, target="")
        else:
            new_row = AlignmentRow(source="", target=right)
        self._new_row = new_row
        self._doc.insert_row(self._row + 1, new_row)

    def undo(self) -> None:
        if self._filled_existing:
            # Clear the cell we filled
            self._doc.set_cell(self._row + 1, self._col, "")
        else:
            # Remove the row we inserted
            self._doc.remove_row(self._row + 1)
        self._doc.set_cell(self._row, self._col, self._original_text)


class MergeCommand(QUndoCommand):
    """Merge active column of current row with the next row.

    Column-only merge:
      - The active column is concatenated (with a single space between
        non-empty parts).
      - If the other column of the next row is blank, the next row is
        removed entirely.
      - If the other column of the next row has content, the next row
        is kept but its active column is cleared (the content was absorbed
        into the current row).
    """

    def __init__(
        self,
        doc: AlignmentDocument,
        row: int,
        col: int,
        *,
        description: str = "Merge",
    ) -> None:
        super().__init__(description)
        self._doc = doc
        self._row = row
        self._col = col
        self._other_col = 1 - col
        # Snapshot originals for undo
        self._orig_active: str = doc.get_cell(row, col)
        self._orig_next_active: str = doc.get_cell(row + 1, col)
        self._orig_next_other: str = doc.get_cell(row + 1, self._other_col)
        self._row_removed: bool = False
        self._removed_row: AlignmentRow | None = None

    def redo(self) -> None:
        next_row_idx = self._row + 1

        # Active column: concatenate with sensible join
        a = self._orig_active
        b = self._orig_next_active
        if a and b:
            merged = a + " " + b
        else:
            merged = a + b  # one is empty, no extra space

        self._doc.set_cell(self._row, self._col, merged)

        # Decide whether to remove or keep the next row
        if self._orig_next_other:
            # Other col has content → keep the row, just clear the active col
            self._row_removed = False
            self._doc.set_cell(next_row_idx, self._col, "")
        else:
            # Other col is blank → remove the entire row
            self._row_removed = True
            self._removed_row = self._doc.rows[next_row_idx]
            self._doc.remove_row(next_row_idx)

    def undo(self) -> None:
        if self._row_removed:
            # Re-insert the removed row
            assert self._removed_row is not None
            self._doc.insert_row(self._row + 1, self._removed_row)
        else:
            # Restore the next row's active column
            self._doc.set_cell(self._row + 1, self._col, self._orig_next_active)

        # Restore current row's active cell
        self._doc.set_cell(self._row, self._col, self._orig_active)


class MoveCellCommand(QUndoCommand):
    """Move a single cell up or down (column-only swap).

    Swaps only the active column's content between adjacent rows;
    the other column stays in place.
    """

    def __init__(
        self,
        doc: AlignmentDocument,
        row: int,
        col: int,
        direction: int,  # -1 = up, +1 = down
        *,
        description: str = "Move cell",
    ) -> None:
        super().__init__(description)
        self._doc = doc
        self._row = row
        self._col = col
        self._direction = direction

    def redo(self) -> None:
        target = self._row + self._direction
        a = self._doc.get_cell(self._row, self._col)
        b = self._doc.get_cell(target, self._col)
        self._doc.set_cell(self._row, self._col, b)
        self._doc.set_cell(target, self._col, a)

    def undo(self) -> None:
        target = self._row + self._direction
        a = self._doc.get_cell(self._row, self._col)
        b = self._doc.get_cell(target, self._col)
        self._doc.set_cell(self._row, self._col, b)
        self._doc.set_cell(target, self._col, a)


class EditCellCommand(QUndoCommand):
    """Replace cell text (after user confirms in edit dialog)."""

    def __init__(
        self,
        doc: AlignmentDocument,
        row: int,
        col: int,
        old_text: str,
        new_text: str,
        *,
        description: str = "Edit cell",
    ) -> None:
        super().__init__(description)
        self._doc = doc
        self._row = row
        self._col = col
        self._old = old_text
        self._new = new_text

    def redo(self) -> None:
        self._doc.set_cell(self._row, self._col, self._new)

    def undo(self) -> None:
        self._doc.set_cell(self._row, self._col, self._old)


class DeleteEmptyRowCommand(QUndoCommand):
    """Delete a row where both source and target are blank."""

    def __init__(
        self,
        doc: AlignmentDocument,
        row: int,
        *,
        description: str = "Delete empty row",
    ) -> None:
        super().__init__(description)
        self._doc = doc
        self._row = row
        self._removed_row: AlignmentRow | None = None

    def redo(self) -> None:
        self._removed_row = self._doc.rows[self._row]
        self._doc.remove_row(self._row)

    def undo(self) -> None:
        assert self._removed_row is not None
        self._doc.insert_row(self._row, self._removed_row)
