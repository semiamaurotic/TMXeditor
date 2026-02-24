"""Application settings management.

Loads/saves shortcuts and per-column font sizes from
``~/.tmxeditor/settings.json``, falling back to bundled defaults.
"""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

_USER_CONFIG_DIR = Path.home() / ".tmxeditor"
_USER_SETTINGS_PATH = _USER_CONFIG_DIR / "settings.json"

# Legacy path (shortcuts only)
_USER_SHORTCUTS_PATH = _USER_CONFIG_DIR / "shortcuts.json"

_loaded: bool = False
_shortcuts: dict[str, str] = {}
_font_sizes: dict[str, int] = {}  # "source" / "target" → pt size
_display: dict[str, object] = {}  # "word_wrap", "column_ratio", etc.

DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 48


# Human-readable labels for actions (used in Settings UI)
ACTION_LABELS: dict[str, str] = {
    "file_open": "Open File",
    "file_save": "Save",
    "file_save_as": "Save As",
    "file_quit": "Quit",
    "edit_undo": "Undo",
    "edit_redo": "Redo",
    "edit_find": "Find / Replace",
    "op_split": "Split Cell (Dialog)",
    "op_merge": "Merge with Next",
    "op_move_up": "Move Cell Up",
    "op_move_down": "Move Cell Down",
    "op_edit_cell": "Edit Cell",
    "op_delete_empty_row": "Delete Empty Row",
}


def _load_defaults() -> dict[str, str]:
    """Load the bundled default shortcuts using importlib.resources.

    Works whether the package is run from source or installed as a wheel.
    """
    try:
        ref = importlib.resources.files("tmxeditor").joinpath("default_shortcuts.json")
        with importlib.resources.as_file(ref) as p:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except (FileNotFoundError, TypeError):
        return {}


def _load_settings() -> dict:
    """Load the user settings file (or legacy shortcuts file)."""
    if _USER_SETTINGS_PATH.exists():
        with open(_USER_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    # Migrate from legacy shortcuts-only file
    if _USER_SHORTCUTS_PATH.exists():
        with open(_USER_SHORTCUTS_PATH, encoding="utf-8") as f:
            return {"shortcuts": json.load(f)}
    return {}


def _load() -> None:
    """Load and merge default + user configs."""
    global _shortcuts, _font_sizes, _loaded
    defaults = _load_defaults()
    user = _load_settings()

    # Shortcuts: defaults overlaid with user overrides
    _shortcuts = dict(defaults)
    if "shortcuts" in user:
        _shortcuts.update(user["shortcuts"])

    # Font sizes
    _font_sizes = {
        "source": DEFAULT_FONT_SIZE,
        "target": DEFAULT_FONT_SIZE,
    }
    if "font_sizes" in user:
        for key in ("source", "target"):
            if key in user["font_sizes"]:
                _font_sizes[key] = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, user["font_sizes"][key]))

    # Display settings
    _display = {
        "word_wrap": True,
        "column_ratio": 0.5,
    }
    if "display" in user:
        _display.update(user["display"])

    _loaded = True


def save_settings() -> None:
    """Persist current shortcuts and font sizes to disk."""
    _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "shortcuts": _shortcuts,
        "font_sizes": _font_sizes,
        "display": _display,
    }
    with open(_USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_shortcuts() -> dict[str, str]:
    """Return the full shortcut mapping (cached after first call)."""
    if not _loaded:
        _load()
    return _shortcuts


def get_shortcut(action: str) -> str:
    """Return the key-sequence string for *action*, or empty string."""
    return get_shortcuts().get(action, "")


def set_shortcuts(mapping: dict[str, str]) -> None:
    """Update the shortcut mapping in memory."""
    global _shortcuts
    _shortcuts.update(mapping)


def get_font_size(column: str) -> int:
    """Return font size for 'source' or 'target' column."""
    if not _loaded:
        _load()
    return _font_sizes.get(column, DEFAULT_FONT_SIZE)


def set_font_size(column: str, size: int) -> None:
    """Set font size for 'source' or 'target' column."""
    if not _loaded:
        _load()
    _font_sizes[column] = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))


def reload() -> None:
    """Force re-read of config files."""
    _load()


def get_display(key: str, default=None):
    """Return a display setting value."""
    if not _loaded:
        _load()
    return _display.get(key, default)


def set_display(key: str, value) -> None:
    """Set a display setting value."""
    if not _loaded:
        _load()
    _display[key] = value
