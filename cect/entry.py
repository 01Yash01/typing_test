"""What each key press does in the exam entry pane, independent of any GUI toolkit.

The entry pane is append-only: text is only ever added at, or removed from, the end. That is how the
exam is locked down. There is no caret movement, selection, cut, paste, undo or Delete, so the only way
to change text is to type, and to Backspace when the exam profile allows it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .keymaps import KeyMap

KEYPAD_CHARS = frozenset("0123456789+-*/.")


@dataclass(frozen=True)
class KeyInput:
    """A key press reduced to what the exam cares about (the GUI layer fills this in)."""

    scan_code: int = 0
    shift: bool = False
    altgr: bool = False
    shortcut: bool = False  # Ctrl or Alt held on their own (AltGr does not count)
    keypad: bool = False
    action: str | None = None  # "backspace", "enter", or None for a character key
    text: str = ""  # what the operating system would type; used for English and the keypad


class EntryPolicy:
    def __init__(self, keymap: KeyMap | None, backspace_allowed: bool, allow_newline: bool = False):
        """`keymap` is the layout to type Hindi with; None means the system keyboard (English)."""
        self.keymap = keymap
        self.backspace_allowed = backspace_allowed
        self.allow_newline = allow_newline

    def handle(self, text: str, key: KeyInput) -> tuple[int, str] | None:
        """Return (characters to delete from the end, text to append) for this key, or None to ignore it."""
        if key.shortcut:
            return None
        if key.action == "backspace":
            return (1, "") if self.backspace_allowed and text else None
        if key.action == "enter":
            return (0, "\n") if self.allow_newline else None
        if key.action is not None:
            return None
        if key.keypad:
            return (0, key.text) if key.text in KEYPAD_CHARS else None
        if self.keymap is None:
            return (0, key.text) if key.text and key.text.isprintable() else None
        tail = text[-self.keymap.max_context:] if self.keymap.max_context else ""
        return self.keymap.press(tail, key.scan_code, key.shift, key.altgr)
