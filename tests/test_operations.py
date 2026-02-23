"""Tests for alignment operations: split, merge, move."""

from __future__ import annotations

from tmxeditor.models import AlignmentDocument, AlignmentRow


class TestSplit:
    def test_split_source_mid(self, sample_doc: AlignmentDocument):
        """Split source of row 0 at position 6 → 'Alpha ' | 'one two'."""
        row = 0
        col = 0
        pos = 6  # after "Alpha "
        original = sample_doc.get_cell(row, col)
        assert original == "Alpha one two"

        left = original[:pos]
        right = original[pos:]
        sample_doc.set_cell(row, col, left)
        sample_doc.insert_row(row + 1, AlignmentRow(source=right, target=""))

        assert sample_doc.row_count() == 5  # was 4, now 5
        assert sample_doc.get_cell(0, 0) == "Alpha "
        assert sample_doc.get_cell(1, 0) == "one two"
        assert sample_doc.get_cell(1, 1) == ""  # target is blank
        # Original target untouched
        assert sample_doc.get_cell(0, 1) == "อัลฟา หนึ่ง สอง"

    def test_split_target_mid(self, sample_doc: AlignmentDocument):
        """Split target of row 0 at position 7."""
        row = 0
        col = 1
        original = sample_doc.get_cell(row, col)
        pos = 7

        left = original[:pos]
        right = original[pos:]
        sample_doc.set_cell(row, col, left)
        sample_doc.insert_row(row + 1, AlignmentRow(source="", target=right))

        assert sample_doc.row_count() == 5
        assert sample_doc.get_cell(0, 1) == original[:pos]
        assert sample_doc.get_cell(1, 1) == original[pos:]
        assert sample_doc.get_cell(1, 0) == ""  # source is blank

    def test_split_does_not_affect_other_column(self, sample_doc: AlignmentDocument):
        """Splitting source column must not change target."""
        original_target = sample_doc.get_cell(0, 1)
        original_source = sample_doc.get_cell(0, 0)
        pos = 5
        sample_doc.set_cell(0, 0, original_source[:pos])
        sample_doc.insert_row(1, AlignmentRow(source=original_source[pos:], target=""))
        assert sample_doc.get_cell(0, 1) == original_target


class TestMerge:
    def test_merge_source_only(self, sample_doc: AlignmentDocument):
        """Merge source of row 0 with row 1 — target stays stable."""
        src0 = sample_doc.get_cell(0, 0)
        src1 = sample_doc.get_cell(1, 0)
        tgt0 = sample_doc.get_cell(0, 1)
        tgt1 = sample_doc.get_cell(1, 1)

        merged = src0 + " " + src1
        sample_doc.set_cell(0, 0, merged)
        sample_doc.remove_row(1)

        assert sample_doc.row_count() == 3
        assert sample_doc.get_cell(0, 0) == "Alpha one two Beta three"
        # Target of row 0 unchanged
        assert sample_doc.get_cell(0, 1) == tgt0
        # Row that was index 2 is now index 1
        assert sample_doc.get_cell(1, 0) == "Gamma four"

    def test_merge_target_only(self, sample_doc: AlignmentDocument):
        """Merge target of row 1 with row 2 — source stays stable."""
        tgt1 = sample_doc.get_cell(1, 1)
        tgt2 = sample_doc.get_cell(2, 1)

        merged = tgt1 + " " + tgt2
        sample_doc.set_cell(1, 1, merged)
        sample_doc.remove_row(2)

        assert sample_doc.row_count() == 3
        assert sample_doc.get_cell(1, 1) == "เบต้า สาม แกมมา สี่"
        # Source of row 1 unchanged
        assert sample_doc.get_cell(1, 0) == "Beta three"

    def test_merge_with_empty(self, sample_doc: AlignmentDocument):
        """Merge where the next cell is empty — no extra whitespace."""
        sample_doc.set_cell(1, 0, "")
        original = sample_doc.get_cell(0, 0)
        merged = original  # empty second part → no space added
        sample_doc.set_cell(0, 0, merged)
        sample_doc.remove_row(1)
        assert sample_doc.get_cell(0, 0) == "Alpha one two"


class TestMove:
    def test_move_down(self, sample_doc: AlignmentDocument):
        src0 = sample_doc.get_cell(0, 0)
        tgt0 = sample_doc.get_cell(0, 1)
        src1 = sample_doc.get_cell(1, 0)
        tgt1 = sample_doc.get_cell(1, 1)

        sample_doc.swap_rows(0, 1)

        assert sample_doc.get_cell(0, 0) == src1
        assert sample_doc.get_cell(0, 1) == tgt1
        assert sample_doc.get_cell(1, 0) == src0
        assert sample_doc.get_cell(1, 1) == tgt0

    def test_move_up(self, sample_doc: AlignmentDocument):
        src2 = sample_doc.get_cell(2, 0)
        tgt2 = sample_doc.get_cell(2, 1)
        src1 = sample_doc.get_cell(1, 0)
        tgt1 = sample_doc.get_cell(1, 1)

        sample_doc.swap_rows(2, 1)

        assert sample_doc.get_cell(1, 0) == src2
        assert sample_doc.get_cell(1, 1) == tgt2
        assert sample_doc.get_cell(2, 0) == src1
        assert sample_doc.get_cell(2, 1) == tgt1

    def test_move_preserves_pair(self, sample_doc: AlignmentDocument):
        """Moving a row must keep source+target together."""
        src3 = sample_doc.get_cell(3, 0)
        tgt3 = sample_doc.get_cell(3, 1)
        sample_doc.swap_rows(3, 2)
        assert sample_doc.get_cell(2, 0) == src3
        assert sample_doc.get_cell(2, 1) == tgt3

    def test_row_count_stable_after_move(self, sample_doc: AlignmentDocument):
        sample_doc.swap_rows(0, 1)
        assert sample_doc.row_count() == 4
