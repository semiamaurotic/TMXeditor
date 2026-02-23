# TMX Alignment Editor

A keyboard-driven desktop application for editing TMX 1.4b translation memories as aligned source/target segment pairs. Built with Python and PySide6 (Qt 6).

## Features

- **Two-column alignment view** — source and target segments side by side
- **Split** — split a segment at any cursor position (single-column, non-cascading)
- **Merge** — merge active column with the row below (other column untouched)
- **Move rows** — reorder translation units up/down
- **Guarded editing** — text changes require explicit entry into edit mode
- **Full undo/redo** — every operation is reversible
- **Find & Replace** — search across both columns
- **Configurable keyboard shortcuts** — via JSON config file
- **Robust file handling** — atomic saves, automatic backups, Unicode support
- **Performance** — virtual scrolling handles 100k+ row files

## Requirements

- Python 3.10+
- macOS (or any platform supported by PySide6)

## Installation

```bash
cd /path/to/TMXeditor

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[test]"
```

## Running

```bash
# Via entry point
tmxeditor

# Or via module
python -m tmxeditor
```

## Running Tests

```bash
pytest tests/ -v
```

## Keyboard Shortcuts

| Action | Default Shortcut |
|---|---|
| Open | Ctrl+O |
| Save | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Quit | Ctrl+Q |
| Undo | Ctrl+Z |
| Redo | Ctrl+Shift+Z |
| Find / Replace | Ctrl+F |
| Split Cell | Ctrl+T |
| Merge with Next | Ctrl+M |
| Move Row Up | Ctrl+Up |
| Move Row Down | Ctrl+Down |
| Edit Cell | F2 |

### Customizing Shortcuts

Create `~/.tmxeditor/shortcuts.json` with your overrides:

```json
{
    "op_split": "Ctrl+Shift+T",
    "op_merge": "Ctrl+Shift+M"
}
```

Only the keys you include will be overridden; all others keep their defaults.

## Project Structure

```
TMXeditor/
├── src/tmxeditor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py          # Entry point
│   ├── main_window.py   # Main window (menus, toolbar, operations)
│   ├── table_model.py   # QAbstractTableModel (virtual scrolling)
│   ├── table_view.py    # QTableView customization
│   ├── dialogs.py       # Edit, Split, Find/Replace dialogs
│   ├── models.py        # AlignmentDocument, AlignmentRow
│   ├── tmx_io.py        # TMX parser & writer
│   ├── config.py        # Shortcut configuration
│   └── undo.py          # Undo/redo commands
├── tests/
│   ├── fixtures/        # TMX test files
│   ├── conftest.py
│   ├── test_tmx_io.py
│   ├── test_operations.py
│   ├── test_undo.py
│   └── test_config.py
├── docs/
│   └── user_guide.md
├── default_shortcuts.json
└── pyproject.toml
```

## License

MIT
