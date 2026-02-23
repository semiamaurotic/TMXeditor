"""Tests for configuration loading and font sizes."""

from __future__ import annotations

from tmxeditor import config


class TestConfig:
    def test_defaults_loaded(self):
        shortcuts = config.get_shortcuts()
        assert isinstance(shortcuts, dict)
        assert len(shortcuts) > 0

    def test_get_shortcut_returns_string(self):
        assert isinstance(config.get_shortcut("file_open"), str)

    def test_unknown_shortcut_returns_empty(self):
        assert config.get_shortcut("__nonexistent__") == ""

    def test_font_size_defaults(self):
        assert config.get_font_size("source") == config.DEFAULT_FONT_SIZE
        assert config.get_font_size("target") == config.DEFAULT_FONT_SIZE

    def test_font_size_set_and_get(self):
        config.set_font_size("source", 20)
        assert config.get_font_size("source") == 20
        # Reset
        config.set_font_size("source", config.DEFAULT_FONT_SIZE)

    def test_font_size_clamped(self):
        config.set_font_size("target", 2)  # below min
        assert config.get_font_size("target") == config.MIN_FONT_SIZE
        config.set_font_size("target", 100)  # above max
        assert config.get_font_size("target") == config.MAX_FONT_SIZE
        # Reset
        config.set_font_size("target", config.DEFAULT_FONT_SIZE)

    def test_action_labels_exist(self):
        assert isinstance(config.ACTION_LABELS, dict)
        assert "file_open" in config.ACTION_LABELS
        assert "op_split" in config.ACTION_LABELS
