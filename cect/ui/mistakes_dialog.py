"""Post-exam word-by-word mistake review. Always word-level, whatever the exam's scoring mode."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..scoring import word_diff
from .style import STYLE

_LABELS = {"wrong": "Wrong", "missing": "Missing", "extra": "Extra"}


class MistakesDialog(QDialog):
    def __init__(self, source: str, typed: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mistake review")
        self.setStyleSheet(STYLE)
        self.resize(520, 420)

        diffs = [d for d in word_diff(source, typed) if d.status != "correct"]
        layout = QVBoxLayout(self)
        self.summary = QLabel(
            "No mistakes found." if not diffs else
            f"{len(diffs)} word{'s' if len(diffs) != 1 else ''} to review "
            "(a word-level check; it does not follow the exam's own scoring mode):"
        )
        layout.addWidget(self.summary)

        self.table = QTableWidget(len(diffs), 3)
        self.table.setHorizontalHeaderLabels(["Issue", "Source word", "You typed"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, diff in enumerate(diffs):
            self.table.setItem(row, 0, QTableWidgetItem(_LABELS[diff.status]))
            self.table.setItem(row, 1, QTableWidgetItem(diff.source or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(diff.typed or "—"))
        layout.addWidget(self.table, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
