"""Tests for undo/redo correctness across all operations."""

from __future__ import annotations

from PySide6.QtGui import QUndoStack

from tmxeditor.models import AlignmentDocument, AlignmentRow
from tmxeditor.undo import (
    DeleteEmptyRowCommand,
    EditCellCommand,
    MergeCommand,
    MoveCellCommand,
    SplitCommand,
)


def _make_doc() -> AlignmentDocument:
    return AlignmentDocument(
        rows=[
            AlignmentRow(source="Alpha one two", target="อัลฟา หนึ่ง สอง"),
            AlignmentRow(source="Beta three", target="เบต้า สาม"),
            AlignmentRow(source="Gamma four", target="แกมมา สี่"),
            AlignmentRow(source="Delta five", target="เดลต้า ห้า"),
        ],
        source_lang="en",
        target_lang="th",
    )


# ── Split ───────────────────────────────────────────────────────


class TestSplitUndoRedo:
    def test_split_inserts_new_row(self):
        """When no blank cell below, split inserts a new row."""
        doc = _make_doc()
        stack = QUndoStack()
        cmd = SplitCommand(doc, row=0, col=0, pos=6)
        stack.push(cmd)

        assert doc.row_count() == 5
        assert doc.get_cell(0, 0) == "Alpha "
        assert doc.get_cell(1, 0) == "one two"
        assert doc.get_cell(1, 1) == ""  # blank target in new row

        stack.undo()
        assert doc.row_count() == 4
        assert doc.get_cell(0, 0) == "Alpha one two"

    def test_split_fills_blank_below(self):
        """When the cell below in the same column is blank, fill it."""
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="Hello world", target="Thai A"),
                AlignmentRow(source="", target="Thai B"),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = SplitCommand(doc, row=0, col=0, pos=6)
        stack.push(cmd)

        # Should NOT insert a new row — fills the existing blank cell
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Hello "
        assert doc.get_cell(1, 0) == "world"
        assert doc.get_cell(1, 1) == "Thai B"  # other column untouched

        stack.undo()
        assert doc.get_cell(0, 0) == "Hello world"
        assert doc.get_cell(1, 0) == ""  # restored to blank

    def test_split_does_not_fill_non_blank(self):
        """When the cell below has content, insert a new row."""
        doc = _make_doc()
        stack = QUndoStack()
        # Row 0 source = "Alpha one two", Row 1 source = "Beta three" (not blank)
        cmd = SplitCommand(doc, row=0, col=0, pos=6)
        stack.push(cmd)
        assert doc.row_count() == 5  # new row inserted

    def test_split_target(self):
        doc = _make_doc()
        stack = QUndoStack()
        cmd = SplitCommand(doc, row=0, col=1, pos=7)
        stack.push(cmd)

        assert doc.row_count() == 5
        assert doc.get_cell(1, 0) == ""  # blank source in new row
        assert doc.get_cell(1, 1) != ""

        stack.undo()
        assert doc.row_count() == 4

    def test_split_redo(self):
        doc = _make_doc()
        stack = QUndoStack()
        cmd = SplitCommand(doc, row=0, col=0, pos=6)
        stack.push(cmd)
        stack.undo()
        stack.redo()
        assert doc.row_count() == 5
        assert doc.get_cell(0, 0) == "Alpha "


# ── Merge ───────────────────────────────────────────────────────


class TestMergeUndoRedo:
    def test_merge_removes_row_when_other_col_blank(self):
        """Merge removes the next row if its other column is blank."""
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="Part A", target="Thai"),
                AlignmentRow(source="Part B", target=""),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = MergeCommand(doc, row=0, col=0)
        stack.push(cmd)

        assert doc.row_count() == 1
        assert doc.get_cell(0, 0) == "Part A Part B"
        assert doc.get_cell(0, 1) == "Thai"

        stack.undo()
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Part A"
        assert doc.get_cell(1, 0) == "Part B"

    def test_merge_keeps_row_when_other_col_has_content(self):
        """Merge keeps the next row (clearing active col) if other col has content."""
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="Part A", target="Thai A"),
                AlignmentRow(source="Part B", target="Thai B"),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = MergeCommand(doc, row=0, col=0)
        stack.push(cmd)

        assert doc.row_count() == 2  # row kept!
        assert doc.get_cell(0, 0) == "Part A Part B"
        assert doc.get_cell(0, 1) == "Thai A"
        assert doc.get_cell(1, 0) == ""  # active col cleared
        assert doc.get_cell(1, 1) == "Thai B"  # other col preserved

        stack.undo()
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Part A"
        assert doc.get_cell(1, 0) == "Part B"
        assert doc.get_cell(1, 1) == "Thai B"

    def test_merge_target_column_only(self):
        """Merging target column does not affect source."""
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="En A", target="Thai A"),
                AlignmentRow(source="En B", target="Thai B"),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = MergeCommand(doc, row=0, col=1)
        stack.push(cmd)

        assert doc.row_count() == 2  # row kept (source has content)
        assert doc.get_cell(0, 1) == "Thai A Thai B"
        assert doc.get_cell(0, 0) == "En A"  # source unchanged
        assert doc.get_cell(1, 1) == ""  # target cleared
        assert doc.get_cell(1, 0) == "En B"  # source preserved

    def test_merge_redo(self):
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="A", target=""),
                AlignmentRow(source="B", target=""),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = MergeCommand(doc, row=0, col=0)
        stack.push(cmd)
        stack.undo()
        stack.redo()
        assert doc.row_count() == 1
        assert doc.get_cell(0, 0) == "A B"


# ── Move Cell ──────────────────────────────────────────────────


class TestMoveCellUndoRedo:
    def test_move_cell_down(self):
        doc = _make_doc()
        stack = QUndoStack()
        orig_src0 = doc.get_cell(0, 0)
        orig_src1 = doc.get_cell(1, 0)
        orig_tgt0 = doc.get_cell(0, 1)  # should NOT change
        orig_tgt1 = doc.get_cell(1, 1)  # should NOT change

        cmd = MoveCellCommand(doc, row=0, col=0, direction=1)
        stack.push(cmd)

        # Source cells swapped
        assert doc.get_cell(0, 0) == orig_src1
        assert doc.get_cell(1, 0) == orig_src0
        # Target cells unchanged
        assert doc.get_cell(0, 1) == orig_tgt0
        assert doc.get_cell(1, 1) == orig_tgt1

        stack.undo()
        assert doc.get_cell(0, 0) == orig_src0
        assert doc.get_cell(1, 0) == orig_src1

    def test_move_cell_up(self):
        doc = _make_doc()
        stack = QUndoStack()
        orig_tgt1 = doc.get_cell(1, 1)
        orig_tgt2 = doc.get_cell(2, 1)
        orig_src1 = doc.get_cell(1, 0)
        orig_src2 = doc.get_cell(2, 0)

        cmd = MoveCellCommand(doc, row=2, col=1, direction=-1)
        stack.push(cmd)

        # Target cells swapped
        assert doc.get_cell(1, 1) == orig_tgt2
        assert doc.get_cell(2, 1) == orig_tgt1
        # Source cells unchanged
        assert doc.get_cell(1, 0) == orig_src1
        assert doc.get_cell(2, 0) == orig_src2

        stack.undo()
        assert doc.get_cell(1, 1) == orig_tgt1
        assert doc.get_cell(2, 1) == orig_tgt2


# ── Edit ────────────────────────────────────────────────────────


class TestEditUndoRedo:
    def test_edit_undo(self):
        doc = _make_doc()
        stack = QUndoStack()
        old = doc.get_cell(0, 0)
        cmd = EditCellCommand(doc, 0, 0, old, "New text")
        stack.push(cmd)
        assert doc.get_cell(0, 0) == "New text"
        stack.undo()
        assert doc.get_cell(0, 0) == old

    def test_edit_redo(self):
        doc = _make_doc()
        stack = QUndoStack()
        old = doc.get_cell(0, 0)
        cmd = EditCellCommand(doc, 0, 0, old, "New text")
        stack.push(cmd)
        stack.undo()
        stack.redo()
        assert doc.get_cell(0, 0) == "New text"


# ── Delete Empty Row ────────────────────────────────────────────


class TestDeleteEmptyRow:
    def test_delete_empty_row(self):
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="A", target="B"),
                AlignmentRow(source="", target=""),
                AlignmentRow(source="C", target="D"),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()
        cmd = DeleteEmptyRowCommand(doc, row=1)
        stack.push(cmd)

        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "A"
        assert doc.get_cell(1, 0) == "C"

        stack.undo()
        assert doc.row_count() == 3
        assert doc.get_cell(1, 0) == ""
        assert doc.get_cell(1, 1) == ""


# ── Sequences ──────────────────────────────────────────────────


class TestSequences:
    def test_split_both_then_merge_realigns(self):
        """Full workflow: split source, split target, merge to realign.

        Start: Row 0 = "Hello world" | "สวัสดีชาวโลก"
        1. Split source at 6 → fills blank? No, only 1 row. Inserts new row.
        2. Split target at 6 on row 0 → fills the blank target in row 1.
        Final:
          Row 0: "Hello " | "สวัสดี"
          Row 1: "world"  | "ชาวโลก"  ← smart fill!
        """
        doc = AlignmentDocument(
            rows=[AlignmentRow(source="Hello world", target="สวัสดีชาวโลก")],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()

        # Step 1: Split source at pos 6
        stack.push(SplitCommand(doc, 0, 0, 6))
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Hello "
        assert doc.get_cell(1, 0) == "world"
        assert doc.get_cell(1, 1) == ""  # blank target

        # Step 2: Split target at pos 6 on row 0
        # Row 1 target is blank → smart fill puts "ชาวโลก" there
        stack.push(SplitCommand(doc, 0, 1, 6))
        assert doc.row_count() == 2  # no new row inserted!
        assert doc.get_cell(0, 1) == "สวัสดี"
        assert doc.get_cell(1, 1) == "ชาวโลก"  # smart fill!
        assert doc.get_cell(1, 0) == "world"  # source untouched

        # Undo both
        stack.undo()
        assert doc.row_count() == 2
        assert doc.get_cell(0, 1) == "สวัสดีชาวโลก"
        assert doc.get_cell(1, 1) == ""  # back to blank

        stack.undo()
        assert doc.row_count() == 1
        assert doc.get_cell(0, 0) == "Hello world"

    def test_merge_then_delete_empty_row(self):
        """Merge leaves blank cell, then delete the empty row."""
        doc = AlignmentDocument(
            rows=[
                AlignmentRow(source="Part A", target="Thai A"),
                AlignmentRow(source="Part B", target="Thai B"),
            ],
            source_lang="en",
            target_lang="th",
        )
        stack = QUndoStack()

        # Merge source → keeps row because target has content
        stack.push(MergeCommand(doc, 0, 0))
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Part A Part B"
        assert doc.get_cell(1, 0) == ""
        assert doc.get_cell(1, 1) == "Thai B"

        # Now merge target of row 0 with row 1
        stack.push(MergeCommand(doc, 0, 1))
        # Row 1 source is blank → row removed
        assert doc.row_count() == 1
        assert doc.get_cell(0, 0) == "Part A Part B"
        assert doc.get_cell(0, 1) == "Thai A Thai B"

        # Undo both
        stack.undo()
        assert doc.row_count() == 2
        stack.undo()
        assert doc.row_count() == 2
        assert doc.get_cell(0, 0) == "Part A"
        assert doc.get_cell(1, 0) == "Part B"

    def test_multiple_cell_moves_undo_all(self):
        doc = _make_doc()
        stack = QUndoStack()
        originals = [doc.get_cell(i, 0) for i in range(4)]

        stack.push(MoveCellCommand(doc, 0, 0, 1))
        stack.push(MoveCellCommand(doc, 1, 0, 1))
        stack.push(MoveCellCommand(doc, 2, 0, 1))

        stack.undo()
        stack.undo()
        stack.undo()

        for i in range(4):
            assert doc.get_cell(i, 0) == originals[i]
