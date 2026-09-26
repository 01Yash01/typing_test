"""The locked-down entry pane.

It is a view of ExamSession.text, never an editor: every key press is reported to the session and the
pane is then redrawn from the session's text. Selection, caret placement, cut, paste, drag and drop,
undo, the context menu and input-method composition are all switched off, so the only way to change
the text is through the session's rules.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextOption
from PySide6.QtWidgets import QPlainTextEdit

from ..entry import KeyInput

_ACTIONS = {
    int(Qt.Key.Key_Backspace): "backspace",
    int(Qt.Key.Key_Return): "enter",
    int(Qt.Key.Key_Enter): "enter",
}


def key_input_from_event(event: QKeyEvent) -> KeyInput:
    mods = event.modifiers()
    ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
    alt = bool(mods & Qt.KeyboardModifier.AltModifier)
    # Windows reports AltGr as Ctrl+Alt; Ctrl or Alt on their own are shortcuts.
    altgr = (ctrl and alt) or bool(mods & Qt.KeyboardModifier.GroupSwitchModifier)
    return KeyInput(
        scan_code=event.nativeScanCode(),
        shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
        altgr=altgr,
        shortcut=(ctrl or alt) and not altgr,
        keypad=bool(mods & Qt.KeyboardModifier.KeypadModifier),
        action=_ACTIONS.get(event.key()),
        text=event.text(),
    )


class ExamEdit(QPlainTextEdit):
    key_input = Signal(object)  # a KeyInput for every key press

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)
        self.setAcceptDrops(False)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setCursorWidth(2)

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.ensureCursorVisible()

    # Everything below refuses the ways of changing text that bypass the session.
    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.key_input.emit(key_input_from_event(event))
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        event.accept()

    def inputMethodEvent(self, event) -> None:
        event.ignore()

    def canInsertFromMimeData(self, source) -> bool:
        return False

    def insertFromMimeData(self, source) -> None:
        pass

    def mousePressEvent(self, event) -> None:
        self.setFocus()  # focus only: no caret placement or selection
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        event.accept()

    def dragEnterEvent(self, event) -> None:
        event.ignore()

    def dropEvent(self, event) -> None:
        event.ignore()

    def focusNextPrevChild(self, next_: bool) -> bool:
        return False  # Tab is just another ignored key, not a way out of the pane

    # Qt's own editing commands are reachable by accessibility tools even though no key or menu offers
    # them; refuse them so the pane can never drift from the session's text.
    def cut(self) -> None:
        pass

    def paste(self) -> None:
        pass

    def undo(self) -> None:
        pass

    def redo(self) -> None:
        pass

    def selectAll(self) -> None:
        pass
