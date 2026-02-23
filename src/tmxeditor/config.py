"""Keyboard-shortcut configuration management.

Loads shortcuts from ``~/.tmxeditor/shortcuts.json``, falling back
to the bundled ``default_shortcuts.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent / "default_shortcuts.json"
_USER_CONFIG_DIR = Path.home() / ".tmxeditor"
_USER_SHORTCUTS_PATH = _USER_CONFIG_DIR / "shortcuts.json"

_shortcuts: dict[str, str] = {}


def _load() -> dict[str, str]:
    """Load and merge default + user shortcut configs."""
    shortcuts: dict[str, str] = {}
    # Load built-in defaults
    if _DEFAULTS_PATH.exists():
        with open(_DEFAULTS_PATH, encoding="utf-8") as f:
            shortcuts.update(json.load(f))
    # Override with user config if present
    if _USER_SHORTCUTS_PATH.exists():
        with open(_USER_SHORTCUTS_PATH, encoding="utf-8") as f:
            shortcuts.update(json.load(f))
    return shortcuts


def get_shortcuts() -> dict[str, str]:
    """Return the full shortcut mapping (cached after first call)."""
    global _shortcuts
    if not _shortcuts:
        _shortcuts = _load()
    return _shortcuts


def get_shortcut(action: str) -> str:
    """Return the key-sequence string for *action*, or empty string."""
    return get_shortcuts().get(action, "")


def reload() -> None:
    """Force re-read of config files (useful after user edits config)."""
    global _shortcuts
    _shortcuts = _load()
