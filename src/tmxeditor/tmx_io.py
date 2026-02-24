"""TMX 1.4b file parser and writer.

Uses lxml for robust XML handling.  Produces faithful round-trip output:
TU attributes, ``<prop>``, ``<note>``, and inline ``<seg>`` children are
preserved from the original file.  Only modified segment text is updated.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from lxml import etree

from tmxeditor.models import AlignmentDocument, AlignmentRow

# ── Parsing ─────────────────────────────────────────────────────


def _seg_text(tuv_elem: etree._Element) -> str:
    """Extract the full text content of a <seg> element.

    Handles both plain text and mixed content (inline tags).
    For mixed content, we concatenate all text nodes (text + tail of children)
    to get the "raw" segment text the user sees.
    """
    seg = tuv_elem.find("seg")
    if seg is None:
        return ""
    # itertext() yields all text content including children's tail text
    return "".join(seg.itertext())


def _normalize_lang(lang: str) -> str:
    """Normalize a language code for comparison (case-insensitive)."""
    return lang.strip().lower()


def _detect_languages(
    tree: etree._ElementTree,
) -> tuple[str, str]:
    """Determine source and target language codes.

    Strategy:
      1. If <header srclang="..."> is present, use it as source language.
      2. Collect all xml:lang values from <tuv> elements.
      3. Source = srclang from header (or most common lang).
      4. Target = second most common lang.

    All language codes are normalized to lowercase for consistent matching.
    """
    root = tree.getroot()
    header = root.find("header")

    # Gather language frequency from TUVs (normalized)
    lang_counter: Counter[str] = Counter()
    for tuv in root.iter("tuv"):
        lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
        if lang:
            lang_counter[_normalize_lang(lang)] += 1

    if len(lang_counter) < 2:
        langs = list(lang_counter.keys())
        if len(langs) == 0:
            return ("en", "th")
        if len(langs) == 1:
            return (langs[0], "unknown")

    # Determine source language
    src_lang = ""
    if header is not None:
        src_lang = _normalize_lang(header.get("srclang", ""))
        # "*all*" is a TMX convention meaning "not specified"
        if src_lang == "*all*":
            src_lang = ""

    if not src_lang:
        # Use most common language as source
        src_lang = lang_counter.most_common(1)[0][0]

    # Determine target language (most common that isn't source)
    tgt_lang = ""
    for lang, _ in lang_counter.most_common():
        if lang != src_lang:
            tgt_lang = lang
            break

    if not tgt_lang:
        tgt_lang = "unknown"

    return (src_lang, tgt_lang)


def parse_tmx(path: str | Path) -> AlignmentDocument:
    """Parse a TMX file into an AlignmentDocument.

    Preserves:
      - Full <tu> elements (attributes, <prop>, <note>, etc.)
      - All TUV elements including non-source/target languages
      - Inline <seg> content (bpt, ept, ph, it, hi, etc.)

    Raises:
        etree.XMLSyntaxError: On malformed XML.
        ValueError: On structural problems.
    """
    path = Path(path)
    tree = etree.parse(str(path))  # noqa: S320 — trusted local file
    root = tree.getroot()

    # Strip namespace if present (some TMX files use a default namespace)
    tag = etree.QName(root.tag).localname if "}" in root.tag else root.tag
    if tag.lower() != "tmx":
        raise ValueError(f"Root element is <{root.tag}>, expected <tmx>")

    source_lang, target_lang = _detect_languages(tree)

    # Capture full header element for round-trip
    header = root.find("header")
    header_attribs: dict[str, str] = {}
    header_element: etree._Element | None = None
    if header is not None:
        header_attribs = dict(header.attrib)
        header_element = copy.deepcopy(header)

    # Parse TUs
    body = root.find("body")
    if body is None:
        raise ValueError("TMX file has no <body> element")

    rows: list[AlignmentRow] = []
    for tu in body.findall("tu"):
        source_text = ""
        target_text = ""
        extra_tuvs: list[etree._Element] = []

        for tuv in tu.findall("tuv"):
            lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
            normalized = _normalize_lang(lang)
            text = _seg_text(tuv)

            if normalized == source_lang:
                source_text = text
            elif normalized == target_lang:
                target_text = text
            else:
                # Preserve TUVs for other languages
                extra_tuvs.append(copy.deepcopy(tuv))

        rows.append(AlignmentRow(
            source=source_text,
            target=target_text,
            tu_element=copy.deepcopy(tu),
            extra_tuvs=extra_tuvs,
        ))

    return AlignmentDocument(
        rows=rows,
        source_lang=source_lang,
        target_lang=target_lang,
        header_attribs=header_attribs,
        header_element=header_element,
        file_path=str(path),
    )


# ── Writing ─────────────────────────────────────────────────────


def _update_seg_text(tuv: etree._Element, new_text: str) -> None:
    """Replace the <seg> element's content with plain text.

    Removes any inline children (bpt, ept, ph, etc.) and sets
    plain text content.
    """
    seg = tuv.find("seg")
    if seg is None:
        seg = etree.SubElement(tuv, "seg")
    # Clear all children and text
    for child in list(seg):
        seg.remove(child)
    seg.text = new_text
    seg.tail = None


def _find_tuv(tu: etree._Element, lang: str) -> etree._Element | None:
    """Find a <tuv> element matching the given language (case-insensitive)."""
    for tuv in tu.findall("tuv"):
        tuv_lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
        if _normalize_lang(tuv_lang) == _normalize_lang(lang):
            return tuv
    return None


def _build_tu_from_row(row: AlignmentRow, source_lang: str, target_lang: str) -> etree._Element:
    """Build a <tu> element from an AlignmentRow.

    If the row has an original tu_element, clone it and update only
    the modified segments.  Otherwise create a minimal new <tu>.
    """
    if row.tu_element is not None:
        tu = copy.deepcopy(row.tu_element)

        # Update source segment if modified
        if row.source_modified:
            src_tuv = _find_tuv(tu, source_lang)
            if src_tuv is not None:
                _update_seg_text(src_tuv, row.source)
            else:
                # Source TUV was missing — create it
                src_tuv = etree.SubElement(tu, "tuv")
                src_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", source_lang)
                _update_seg_text(src_tuv, row.source)

        # Update target segment if modified
        if row.target_modified:
            tgt_tuv = _find_tuv(tu, target_lang)
            if tgt_tuv is not None:
                _update_seg_text(tgt_tuv, row.target)
            else:
                tgt_tuv = etree.SubElement(tu, "tuv")
                tgt_tuv.set("{http://www.w3.org/XML/1998/namespace}lang", target_lang)
                _update_seg_text(tgt_tuv, row.target)

        return tu

    # New row (e.g., from split) — create minimal TU
    tu = etree.Element("tu")

    tuv_src = etree.SubElement(tu, "tuv")
    tuv_src.set("{http://www.w3.org/XML/1998/namespace}lang", source_lang)
    seg_src = etree.SubElement(tuv_src, "seg")
    seg_src.text = row.source

    tuv_tgt = etree.SubElement(tu, "tuv")
    tuv_tgt.set("{http://www.w3.org/XML/1998/namespace}lang", target_lang)
    seg_tgt = etree.SubElement(tuv_tgt, "seg")
    seg_tgt.text = row.target

    # Append any extra TUVs (shouldn't exist for new rows, but be safe)
    for extra in row.extra_tuvs:
        tu.append(copy.deepcopy(extra))

    return tu


def write_tmx(
    doc: AlignmentDocument,
    path: str | Path,
    *,
    backup: bool = True,
) -> None:
    """Write an AlignmentDocument to a TMX file atomically.

    Round-trip preservation:
      - If a row has an original <tu> element, it is cloned and only
        modified <seg> content is updated.
      - TU attributes, <prop>, <note>, and unchanged inline tags
        are preserved from the original element.

    Atomic write:
      1. Writes to a temporary file in the same directory.
      2. Uses os.replace() to atomically swap into place.
      3. If *backup* is True and the target file exists, creates a
         .bak copy before overwriting.
    """
    path = Path(path)
    target_dir = path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    # Build XML tree
    root = etree.Element("tmx", version="1.4")

    # Rebuild header: use preserved element if available, else build from attribs
    if doc.header_element is not None:
        header = copy.deepcopy(doc.header_element)
        # Update srclang to match current document
        header.set("srclang", doc.source_lang)
        root.append(header)
    else:
        h_attribs = dict(doc.header_attribs)
        h_attribs.setdefault("creationtool", "TMXEditor")
        h_attribs.setdefault("creationtoolversion", "0.1.0")
        h_attribs.setdefault("segtype", "sentence")
        h_attribs.setdefault("o-tmf", "TMXEditor")
        h_attribs.setdefault("adminlang", "en")
        h_attribs.setdefault("srclang", doc.source_lang)
        h_attribs.setdefault("datatype", "plaintext")
        h_attribs["srclang"] = doc.source_lang
        etree.SubElement(root, "header", **h_attribs)

    body = etree.SubElement(root, "body")
    for row in doc.rows:
        tu = _build_tu_from_row(row, doc.source_lang, doc.target_lang)
        body.append(tu)

    # Serialize
    xml_bytes = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )

    # Atomic write: temp file → os.replace()
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target_dir), suffix=".tmx.tmp"
    )
    try:
        os.write(fd, xml_bytes)
        os.close(fd)
        fd = -1  # mark as closed

        # Backup existing file
        if backup and path.exists():
            bak_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(str(path), str(bak_path))

        os.replace(tmp_path, str(path))
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
