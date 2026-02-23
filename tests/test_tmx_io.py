"""Tests for TMX parsing and writing (round-trip integrity)."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from tmxeditor.models import AlignmentDocument
from tmxeditor.tmx_io import parse_tmx, write_tmx


class TestParsing:
    def test_small_row_count(self, small_doc: AlignmentDocument):
        assert small_doc.row_count() == 5

    def test_small_languages(self, small_doc: AlignmentDocument):
        assert small_doc.source_lang == "en"
        assert small_doc.target_lang == "th"

    def test_small_first_row(self, small_doc: AlignmentDocument):
        assert small_doc.rows[0].source == "Hello world"
        assert small_doc.rows[0].target == "สวัสดีชาวโลก"

    def test_small_last_row(self, small_doc: AlignmentDocument):
        assert small_doc.rows[4].source == "What is your name?"
        assert small_doc.rows[4].target == "คุณชื่ออะไร"

    def test_realistic_row_count(self, realistic_tmx_path: Path):
        doc = parse_tmx(realistic_tmx_path)
        assert doc.row_count() == 50

    def test_realistic_unicode(self, realistic_tmx_path: Path):
        doc = parse_tmx(realistic_tmx_path)
        # Row with degree symbol
        temp_row = [r for r in doc.rows if "27°C" in r.source]
        assert len(temp_row) == 1
        assert "27°C" in temp_row[0].target

    def test_realistic_ampersand(self, realistic_tmx_path: Path):
        doc = parse_tmx(realistic_tmx_path)
        amp_row = [r for r in doc.rows if "Conditions" in r.source]
        assert len(amp_row) == 1
        assert "Terms & Conditions" in amp_row[0].source

    def test_malformed_xml_raises(self, malformed_tmx_path: Path):
        with pytest.raises(etree.XMLSyntaxError):
            parse_tmx(malformed_tmx_path)


class TestRoundTrip:
    def test_parse_save_reparse(self, small_doc: AlignmentDocument, tmp_path: Path):
        out = tmp_path / "output.tmx"
        write_tmx(small_doc, out, backup=False)

        doc2 = parse_tmx(out)
        assert doc2.row_count() == small_doc.row_count()
        assert doc2.source_lang == small_doc.source_lang
        assert doc2.target_lang == small_doc.target_lang
        for r1, r2 in zip(small_doc.rows, doc2.rows):
            assert r1.source == r2.source
            assert r1.target == r2.target

    def test_realistic_round_trip(self, realistic_tmx_path: Path, tmp_path: Path):
        doc1 = parse_tmx(realistic_tmx_path)
        out = tmp_path / "realistic_out.tmx"
        write_tmx(doc1, out, backup=False)

        doc2 = parse_tmx(out)
        assert doc2.row_count() == doc1.row_count()
        for r1, r2 in zip(doc1.rows, doc2.rows):
            assert r1.source == r2.source
            assert r1.target == r2.target

    def test_output_is_valid_xml(self, small_doc: AlignmentDocument, tmp_path: Path):
        out = tmp_path / "valid.tmx"
        write_tmx(small_doc, out, backup=False)
        # Should parse without error
        tree = etree.parse(str(out))
        root = tree.getroot()
        assert root.tag == "tmx"
        assert root.get("version") == "1.4"

    def test_backup_created(self, small_doc: AlignmentDocument, tmp_path: Path):
        out = tmp_path / "backup_test.tmx"
        # First save — no backup needed (file doesn't exist yet)
        write_tmx(small_doc, out, backup=True)
        assert out.exists()
        bak = out.with_suffix(".tmx.bak")
        assert not bak.exists()

        # Second save — backup of first version
        write_tmx(small_doc, out, backup=True)
        assert bak.exists()

    def test_unicode_round_trip_thai(self, tmp_path: Path):
        from tmxeditor.models import AlignmentRow

        doc = AlignmentDocument(
            rows=[
                AlignmentRow(
                    source="Complex Thai text",
                    target="กรุงเทพมหานคร อมรรัตนโกสินทร์ มหินทรายุธยามหาดิลก ภพนพรัตน์ ราชธานีบุรีรมย์",
                ),
            ],
            source_lang="en",
            target_lang="th",
        )
        out = tmp_path / "thai.tmx"
        write_tmx(doc, out, backup=False)
        doc2 = parse_tmx(out)
        assert doc2.rows[0].target == doc.rows[0].target
