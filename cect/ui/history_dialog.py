"""Past attempts, most recent first."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QDialog, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from ..history import HistoryEntry
from .style import STYLE

_COLUMNS = ["Date", "Exam", "Layout", "Duration", "Net WPM", "Accuracy", "Result"]


def _row(entry: HistoryEntry) -> list[str]:
    minutes = entry.duration_seconds // 60
    return [
        time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.timestamp)),
        entry.profile_name,
        entry.layout_name,
        f"{minutes} min",
        f"{entry.net_wpm:.2f}",
        f"{entry.accuracy:.2f} %",
        "Passed" if entry.passed else "Not qualified",
    ]


class HistoryDialog(QDialog):
    def __init__(self, entries: list[HistoryEntry], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Test history")
        self.setStyleSheet(STYLE)
        self.resize(720, 420)

        ordered = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        layout = QVBoxLayout(self)
        self.summary = QLabel("No tests recorded yet." if not ordered else f"{len(ordered)} test(s) on this machine:")
        layout.addWidget(self.summary)

        self.table = QTableWidget(len(ordered), len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, entry in enumerate(ordered):
            for col, text in enumerate(_row(entry)):
                self.table.setItem(row, col, QTableWidgetItem(text))
        layout.addWidget(self.table, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
