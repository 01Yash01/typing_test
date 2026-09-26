"""The screen shown before each exam: which exam, keyboard layout, duration, Backspace rule and passage."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QPushButton, QVBoxLayout

from ..history import load_history
from ..passages import load_passages
from ..profile import ExamProfile
from ..setup import DURATIONS, SetupChoice, layouts_for
from .history_dialog import HistoryDialog
from .style import STYLE


def _select(box: QComboBox, data) -> None:
    index = box.findData(data)
    if index >= 0:
        box.setCurrentIndex(index)


class SetupDialog(QDialog):
    def __init__(self, profiles: dict[str, ExamProfile], saved: dict | None = None, history_loader=load_history, parent=None):
        super().__init__(parent)
        self.profiles = profiles
        self.history_loader = history_loader  # injectable so tests can point it at a temp file
        self.setWindowTitle("New typing test")
        self.setMinimumWidth(460)
        self.setStyleSheet(STYLE)

        self.profile_box = QComboBox()
        for profile_id, profile in sorted(profiles.items(), key=lambda item: (item[1].language != "hindi", item[1].name)):
            self.profile_box.addItem(profile.name, profile_id)  # Hindi first: it is the exam this app is for
        self.layout_box = QComboBox()
        self.duration_box = QComboBox()
        self.backspace_box = QCheckBox("Allow the Backspace key")
        self.passage_box = QComboBox()

        form = QFormLayout()
        form.addRow("Exam:", self.profile_box)
        form.addRow("Keyboard layout:", self.layout_box)
        form.addRow("Duration:", self.duration_box)
        form.addRow("", self.backspace_box)
        form.addRow("Passage:", self.passage_box)

        history, start, quit_ = QPushButton("History"), QPushButton("Start exam"), QPushButton("Quit")
        start.setDefault(True)
        history.clicked.connect(self._show_history)
        start.clicked.connect(self.accept)
        quit_.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(history)
        buttons.addStretch()
        buttons.addWidget(quit_)
        buttons.addWidget(start)
        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addLayout(buttons)

        self.profile_box.currentIndexChanged.connect(self._on_profile)
        saved = saved or {}
        _select(self.profile_box, saved.get("profile_id"))
        self._on_profile()
        _select(self.layout_box, saved.get("layout_id"))
        _select(self.duration_box, saved.get("duration_seconds"))
        _select(self.passage_box, saved.get("passage_id"))
        if isinstance(saved.get("backspace_allowed"), bool):
            self.backspace_box.setChecked(saved["backspace_allowed"])

    @property
    def profile(self) -> ExamProfile:
        return self.profiles[self.profile_box.currentData()]

    def _show_history(self) -> None:
        HistoryDialog(self.history_loader(), self).exec()

    def _on_profile(self) -> None:
        """Refill the choices that depend on the exam: layouts, default duration, Backspace, passages."""
        profile = self.profile
        self.layout_box.clear()
        for layout_id, name in layouts_for(profile.language):
            self.layout_box.addItem(name, layout_id)
        self.duration_box.clear()
        for seconds, label in DURATIONS:
            text = f"{label} ({profile.duration_seconds // 60} min)" if seconds is None else label
            self.duration_box.addItem(text, seconds)
        self.backspace_box.setChecked(profile.backspace_allowed)
        self.passage_box.clear()
        self.passage_box.addItem("Random (long enough for the time)", None)
        for passage in load_passages(profile.language):
            self.passage_box.addItem(f"{passage.title} ({passage.word_count} words)", passage.id)

    def choice(self) -> SetupChoice:
        return SetupChoice(
            profile_id=self.profile_box.currentData(),
            layout_id=self.layout_box.currentData(),
            duration_seconds=self.duration_box.currentData(),
            backspace_allowed=self.backspace_box.isChecked(),
            passage_id=self.passage_box.currentData(),
        )
