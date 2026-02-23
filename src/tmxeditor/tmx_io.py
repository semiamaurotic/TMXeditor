"""TMX 1.4b file parser and writer.

Uses lxml for robust XML handling.  Produces minimal valid TMX output
suitable for translation-memory use (preserves language labels and
segment text; optional metadata is carried through the header attributes
but not guaranteed).
"""

from __future__ import annotations

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


def _detect_languages(
    tree: etree._ElementTree,
) -> tuple[str, str]:
    """Determine source and target language codes.

    Strategy:
      1. If <header srclang="..."> is present, use it as source language.
      2. Collect all xml:lang values from <tuv> elements.
      3. Source = srclang from header (or most common lang).
      4. Target = second most common lang.
    """
    root = tree.getroot()
    header = root.find("header")

    # Gather language frequency from TUVs
    lang_counter: Counter[str] = Counter()
    for tuv in root.iter("tuv"):
        lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
        if lang:
            lang_counter[lang] = lang_counter.get(lang, 0) + 1

    if len(lang_counter) < 2:
        langs = list(lang_counter.keys())
        if len(langs) == 0:
            return ("en", "th")
        if len(langs) == 1:
            return (langs[0], "unknown")

    # Determine source language
    src_lang = ""
    if header is not None:
        src_lang = header.get("srclang", "").strip()
        # "*all*" is a TMX convention meaning "not specified"
        if src_lang.lower() == "*all*":
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

    # Capture header attributes for round-trip
    header = root.find("header")
    header_attribs: dict[str, str] = {}
    if header is not None:
        header_attribs = dict(header.attrib)

    # Parse TUs
    body = root.find("body")
    if body is None:
        raise ValueError("TMX file has no <body> element")

    rows: list[AlignmentRow] = []
    for tu in body.findall("tu"):
        source_text = ""
        target_text = ""
        for tuv in tu.findall("tuv"):
            lang = tuv.get("{http://www.w3.org/XML/1998/namespace}lang") or tuv.get("lang", "")
            text = _seg_text(tuv)
            if lang == source_lang:
                source_text = text
            elif lang == target_lang:
                target_text = text
            # If neither matches (extra language), we skip it
        rows.append(AlignmentRow(source=source_text, target=target_text))

    return AlignmentDocument(
        rows=rows,
        source_lang=source_lang,
        target_lang=target_lang,
        header_attribs=header_attribs,
        file_path=str(path),
    )


# ── Writing ─────────────────────────────────────────────────────


def write_tmx(
    doc: AlignmentDocument,
    path: str | Path,
    *,
    backup: bool = True,
) -> None:
    """Write an AlignmentDocument to a TMX file atomically.

    1. Writes to a temporary file in the same directory.
    2. Uses os.replace() to atomically swap into place.
    3. If *backup* is True and the target file already exists, creates a
       .bak copy before overwriting.
    """
    path = Path(path)
    target_dir = path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    # Build XML tree
    root = etree.Element("tmx", version="1.4")

    # Rebuild header with preserved attributes
    h_attribs = dict(doc.header_attribs)  # copy
    # Ensure required attributes have sensible defaults
    h_attribs.setdefault("creationtool", "TMXEditor")
    h_attribs.setdefault("creationtoolversion", "0.1.0")
    h_attribs.setdefault("segtype", "sentence")
    h_attribs.setdefault("o-tmf", "TMXEditor")
    h_attribs.setdefault("adminlang", "en")
    h_attribs.setdefault("srclang", doc.source_lang)
    h_attribs.setdefault("datatype", "plaintext")
    # Update srclang to match current document
    h_attribs["srclang"] = doc.source_lang
    header = etree.SubElement(root, "header", **h_attribs)  # noqa: F841

    body = etree.SubElement(root, "body")
    for row in doc.rows:
        tu = etree.SubElement(body, "tu")

        tuv_src = etree.SubElement(tu, "tuv")
        tuv_src.set("{http://www.w3.org/XML/1998/namespace}lang", doc.source_lang)
        seg_src = etree.SubElement(tuv_src, "seg")
        seg_src.text = row.source

        tuv_tgt = etree.SubElement(tu, "tuv")
        tuv_tgt.set("{http://www.w3.org/XML/1998/namespace}lang", doc.target_lang)
        seg_tgt = etree.SubElement(tuv_tgt, "seg")
        seg_tgt.text = row.target

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
