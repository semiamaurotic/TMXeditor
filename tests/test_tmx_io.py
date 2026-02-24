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


class TestMetadataPreservation:
    """Tests for TU/TUV metadata round-trip preservation."""

    def test_tu_attributes_preserved(self, metadata_tmx_path: Path, tmp_path: Path):
        """TU attributes (tuid, changedate, etc.) survive round-trip."""
        doc = parse_tmx(metadata_tmx_path)
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        tus = tree.getroot().find("body").findall("tu")
        assert tus[0].get("tuid") == "1"
        assert tus[0].get("changedate") == "20240115T120000Z"
        assert tus[0].get("changeid") == "translator_a"
        assert tus[0].get("creationdate") == "20231201T090000Z"
        assert tus[0].get("usagecount") == "47"

    def test_tu_props_preserved(self, metadata_tmx_path: Path, tmp_path: Path):
        """TU <prop> elements survive round-trip."""
        doc = parse_tmx(metadata_tmx_path)
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        tu = tree.getroot().find("body").findall("tu")[0]
        props = tu.findall("prop")
        assert any(p.get("type") == "x-context" and p.text == "chapter_1" for p in props)

    def test_tu_notes_preserved(self, metadata_tmx_path: Path, tmp_path: Path):
        """TU <note> elements survive round-trip."""
        doc = parse_tmx(metadata_tmx_path)
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        tu = tree.getroot().find("body").findall("tu")[0]
        notes = tu.findall("note")
        assert any("senior translator" in (n.text or "") for n in notes)

    def test_header_props_preserved(self, metadata_tmx_path: Path, tmp_path: Path):
        """Header <prop> and <note> elements survive round-trip."""
        doc = parse_tmx(metadata_tmx_path)
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        header = tree.getroot().find("header")
        props = header.findall("prop")
        assert any(p.get("type") == "x-project" for p in props)
        notes = header.findall("note")
        assert any("Project-level note" in (n.text or "") for n in notes)

    def test_modified_segment_updated(self, metadata_tmx_path: Path, tmp_path: Path):
        """When source text is modified, <seg> content updates but metadata stays."""
        doc = parse_tmx(metadata_tmx_path)
        doc.set_cell(0, 0, "Modified hello")  # modifies source
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        doc2 = parse_tmx(out)
        assert doc2.rows[0].source == "Modified hello"
        # TU attributes still present
        assert doc2.rows[0].tu_element is not None
        assert doc2.rows[0].tu_element.get("tuid") == "1"

    def test_unmodified_segment_preserves_inline(self, metadata_tmx_path: Path, tmp_path: Path):
        """Unmodified segments keep inline tags (bpt, ept, etc.)."""
        doc = parse_tmx(metadata_tmx_path)
        # Row 1 has inline tags — DON'T modify it
        out = tmp_path / "meta_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        tus = tree.getroot().find("body").findall("tu")
        tu2 = tus[1]  # TU with inline tags
        src_tuv = tu2.findall("tuv")[0]
        seg = src_tuv.find("seg")
        bpt_elements = seg.findall("bpt")
        ept_elements = seg.findall("ept")
        assert len(bpt_elements) == 1
        assert len(ept_elements) == 1

    def test_case_insensitive_language(self, metadata_tmx_path: Path):
        """Parser handles mixed-case language codes (EN vs en)."""
        doc = parse_tmx(metadata_tmx_path)
        # Header says srclang="EN", TUVs say xml:lang="EN"
        assert doc.source_lang == "en"  # normalized to lowercase
        assert doc.target_lang == "th"
        # Content parsed correctly despite case
        assert doc.rows[0].source == "Hello world"
        assert doc.rows[0].target == "สวัสดีชาวโลก"


class TestMultilingualPreservation:
    """Tests for extra language TUV preservation."""

    def test_extra_tuvs_preserved(self, metadata_tmx_path: Path, tmp_path: Path):
        """TUVs for languages beyond source/target survive round-trip."""
        doc = parse_tmx(metadata_tmx_path)
        # Row 2 (TU 3) has zh and ja TUVs
        assert len(doc.rows[2].extra_tuvs) == 2

        out = tmp_path / "multi_out.tmx"
        write_tmx(doc, out, backup=False)

        tree = etree.parse(str(out))
        tu3 = tree.getroot().find("body").findall("tu")[2]
        tuvs = tu3.findall("tuv")
        langs = set()
        for tuv in tuvs:
            lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
            langs.add(lang.lower())
        assert "zh" in langs
        assert "ja" in langs
        assert "en" in langs
        assert "th" in langs

    def test_extra_tuv_content_intact(self, metadata_tmx_path: Path, tmp_path: Path):
        """Extra TUV segment text is preserved correctly."""
        doc = parse_tmx(metadata_tmx_path)
        out = tmp_path / "multi_out.tmx"
        write_tmx(doc, out, backup=False)

        doc2 = parse_tmx(out)
        # The zh and ja TUVs are in extra_tuvs
        zh_tuvs = [t for t in doc2.rows[2].extra_tuvs
                    if "zh" in (t.get("{http://www.w3.org/XML/1998/namespace}lang") or "").lower()]
        assert len(zh_tuvs) == 1
        seg = zh_tuvs[0].find("seg")
        assert seg is not None
        assert seg.text == "多语言"

