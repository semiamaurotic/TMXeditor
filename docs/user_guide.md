# TMX Alignment Editor — User Guide

## Overview

TMX Alignment Editor is a keyboard-driven tool for maintaining TMX 1.4b translation memories. It displays source and target segments side by side and lets you split, merge, reorder, and edit segment pairs.

## Getting Started

1. **Launch** the application: `tmxeditor` or `python -m tmxeditor`
2. **Open** a TMX file: **Ctrl+O** (File → Open)
3. The editor shows two columns — Source and Target — with row numbers on the left
4. The **status bar** shows: filename, row count, language pair, and current position

## Navigation

| Action | Shortcut |
|---|---|
| Move to next row | ↓ (Down) |
| Move to previous row | ↑ (Up) |
| Switch between Source/Target column | Tab |

## Core Operations

### Split a Segment

Splits one cell at a cursor position. Only the active column is affected.

1. Navigate to the cell you want to split
2. Press **Ctrl+T** (Operations → Split Cell)
3. In the dialog, position your cursor at the desired split point
4. Press **OK**
5. Result: current cell keeps text before the cursor; a new row is inserted below with the remaining text. The opposite column's new cell is blank.

### Merge with Next Row

Merges the active column of the current row with the row below. Only the active column is concatenated.

1. Navigate to the cell you want to merge
2. Press **Ctrl+M** (Operations → Merge with Next)
3. Result: text is concatenated (with a space between non-empty parts). The other column is not changed. The row below is removed.

### Move Row Up/Down

Reorders translation units. The entire pair (source + target) moves together.

- **Ctrl+↑** — Move current row up
- **Ctrl+↓** — Move current row down

### Edit a Segment

Editing is guarded to prevent accidental changes. Typing in the grid does nothing.

1. Navigate to the cell you want to edit
2. Press **F2** (Operations → Edit Cell)
3. Modify the text in the dialog
4. Press **OK** to confirm, or **Cancel** / **Escape** to discard changes

### Find & Replace

- **Ctrl+F** — Open Find/Replace dialog
- Type a search term and click **Find Next** / **Find Previous**
- Use the **Replace** / **Replace All** buttons as needed
- Toggle **Case sensitive** as needed

## Undo / Redo

Every operation (split, merge, move, edit) is undoable:

- **Ctrl+Z** — Undo
- **Ctrl+Shift+Z** — Redo

## Saving

- **Ctrl+S** — Save (overwrites the current file)
- **Ctrl+Shift+S** — Save As (new file)
- A `.bak` backup is created automatically when overwriting an existing file
- The save is atomic — a temporary file is written first, then swapped into place

## Workflow Example

A typical alignment-correction session:

1. Open a TMX file (Ctrl+O)
2. Navigate to a misaligned row
3. Split the source segment at the correct boundary (Ctrl+T)
4. Move to the target column (Tab), split the target at its boundary (Ctrl+T)
5. If a row has an extra blank, merge it with the row below (Ctrl+M)
6. Reorder rows if needed (Ctrl+↑ / Ctrl+↓)
7. Fix any text errors via edit mode (F2)
8. Save (Ctrl+S)

## Known Limitations

- **Two languages only** — files with more than two languages will use the two most frequent
- **No inline tag rendering** — TMX inline tags (bpt/ept/ph) are displayed as raw text
- **No rich metadata** — change-tracking and historical metadata is not preserved on output
- **Split dialog** — cursor positioning is text-based; no visual marker in the cell itself
- **Find wraps** — search wraps around if no match is found ahead
