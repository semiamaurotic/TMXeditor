"""Tests for configuration / shortcut loading."""

from __future__ import annotations

from tmxeditor import config


class TestConfig:
    def test_defaults_loaded(self):
        config.reload()
        shortcuts = config.get_shortcuts()
        assert "file_open" in shortcuts
        assert "op_split" in shortcuts
        assert "edit_undo" in shortcuts

    def test_get_shortcut_returns_string(self):
        config.reload()
        sc = config.get_shortcut("file_open")
        assert isinstance(sc, str)
        assert len(sc) > 0

    def test_unknown_shortcut_returns_empty(self):
        config.reload()
        sc = config.get_shortcut("nonexistent_action")
        assert sc == ""
