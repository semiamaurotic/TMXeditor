"""Shared pytest fixtures for TMX editor tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tmxeditor.models import AlignmentDocument, AlignmentRow
from tmxeditor.tmx_io import parse_tmx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def small_tmx_path() -> Path:
    return FIXTURES_DIR / "small.tmx"


@pytest.fixture
def realistic_tmx_path() -> Path:
    return FIXTURES_DIR / "realistic.tmx"


@pytest.fixture
def malformed_tmx_path() -> Path:
    return FIXTURES_DIR / "malformed.tmx"


@pytest.fixture
def small_doc(small_tmx_path: Path) -> AlignmentDocument:
    return parse_tmx(small_tmx_path)


@pytest.fixture
def sample_doc() -> AlignmentDocument:
    """A simple in-memory document for unit tests (no file I/O)."""
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
