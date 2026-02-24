"""Data models for the TMX alignment editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml import etree


@dataclass
class AlignmentRow:
    """One aligned source/target pair (one TU).

    Preserves the original ``<tu>`` element for faithful round-trip
    output.  When text is modified, only the ``<seg>`` content is
    updated at write time; all TU attributes, ``<prop>``, ``<note>``,
    and inline TUV elements are kept intact.
    """

    source: str = ""
    target: str = ""

    # Original <tu> element for round-trip preservation (None for new rows)
    tu_element: etree._Element | None = field(default=None, repr=False)

    # TUVs for languages beyond source/target (preserved verbatim)
    extra_tuvs: list[etree._Element] = field(default_factory=list, repr=False)

    # Track which columns were modified (for selective <seg> updates)
    source_modified: bool = field(default=False, repr=False)
    target_modified: bool = field(default=False, repr=False)


@dataclass
class AlignmentDocument:
    """In-memory representation of a TMX file as aligned rows."""

    rows: list[AlignmentRow] = field(default_factory=list)
    source_lang: str = "en"
    target_lang: str = "th"
    # Preserved header attributes for faithful round-trip output
    header_attribs: dict[str, str] = field(default_factory=dict)
    # Preserved full <header> element (includes <prop>/<note> children)
    header_element: etree._Element | None = field(default=None, repr=False)
    file_path: str | None = None

    # ── Row access helpers ──────────────────────────────────────

    def row_count(self) -> int:
        return len(self.rows)

    def get_cell(self, row: int, col: int) -> str:
        """Return cell text.  col 0 = source, col 1 = target."""
        r = self.rows[row]
        return r.source if col == 0 else r.target

    def set_cell(self, row: int, col: int, text: str) -> None:
        r = self.rows[row]
        if col == 0:
            r.source = text
            r.source_modified = True
        else:
            r.target = text
            r.target_modified = True

    # ── Structural operations ───────────────────────────────────

    def insert_row(self, index: int, row: AlignmentRow) -> None:
        self.rows.insert(index, row)

    def remove_row(self, index: int) -> AlignmentRow:
        return self.rows.pop(index)
