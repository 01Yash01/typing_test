"""The exam screen: source text on top, entry pane below (the TCS iON-style vertical split).

No error is ever shown while typing. The only feedback is the countdown; the score appears on submit.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from ..history import HistoryEntry, append_history
from ..profile import ExamProfile
from ..scoring import ScoreResult
from ..session import FINISHED, READY, ExamSession
from .exam_edit import ExamEdit
from .mistakes_dialog import MistakesDialog
from .style import STYLE


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes:02d}:{secs:02d}"


class ScoreDialog(QDialog):
    new_test = Signal()

    def __init__(self, result: ScoreResult, profile: ExamProfile, source: str, typed: str, parent=None):
        super().__init__(parent)
        self.source, self.typed = source, typed
        self.setWindowTitle("Examination scorecard")
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        verdict = QLabel("PASSED (QUALIFIED)" if result.passed else "NOT QUALIFIED")
        verdict.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {'#15803d' if result.passed else '#b91c1c'};")
        layout.addWidget(verdict)
        form = QFormLayout()
        rows = [
            ("Net speed", f"{result.net_wpm:.2f} WPM  (required {profile.min_net_wpm:g})"),
            ("Accuracy", f"{result.accuracy:.2f} %  (required {profile.min_accuracy:g} %)"),
            ("Gross speed", f"{result.gross_wpm:.2f} WPM"),
            ("Keystrokes typed", str(result.total_keystrokes)),
            ("Keystrokes credited", str(result.correct_keystrokes)),
            ("Mistakes", f"{result.mistakes} {result.mistake_unit}"),
            ("Time used", f"{format_duration(result.elapsed_seconds)} of {format_duration(profile.duration_seconds)}"),
            ("Scoring", f"{profile.scoring} mode, 5 keystrokes = 1 word"),
        ]
        for label, value in rows:
            form.addRow(f"{label}:", QLabel(value))
        layout.addLayout(form)
        buttons = QHBoxLayout()
        mistakes, again, close = QPushButton("Review mistakes"), QPushButton("New test"), QPushButton("Close")
        mistakes.clicked.connect(self._show_mistakes)
        again.clicked.connect(self.new_test)
        again.clicked.connect(self.accept)
        close.clicked.connect(self.accept)
        buttons.addWidget(mistakes)
        buttons.addStretch()
        buttons.addWidget(again)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _show_mistakes(self) -> None:
        MistakesDialog(self.source, self.typed, self).exec()


class ExamWindow(QMainWindow):
    new_test = Signal()

    def __init__(
        self, session: ExamSession, layout_name: str, font_family: str, font_note: str = "",
        history_path=None, parent=None,
    ):
        super().__init__(parent)
        self.session = session
        self.layout_name = layout_name
        self.history_path = history_path  # None means the real per-user history file
        self.score_dialog: ScoreDialog | None = None
        profile = session.profile
        self.setWindowTitle(f"{profile.name} - typing examination simulator")
        self.resize(1000, 700)
        self.setStyleSheet(STYLE)

        root = QWidget()
        self.setCentralWidget(root)
        column = QVBoxLayout(root)
        column.setContentsMargins(0, 0, 0, 12)

        header = QFrame()
        header.setObjectName("header")
        bar = QHBoxLayout(header)
        title = QLabel(f"{profile.name.upper()}  |  {layout_name}")
        self.timer_label = QLabel()
        self.timer_label.setObjectName("timer")
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("start")
        self.start_button.setVisible(profile.timer_start == "start_button")
        bar.addWidget(title)
        bar.addStretch()
        bar.addWidget(self.start_button)
        bar.addWidget(self.timer_label)
        column.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(16, 8, 16, 0)
        column.addLayout(body, 1)
        self.notice = QLabel(font_note)
        self.notice.setObjectName("notice")
        self.notice.setVisible(bool(font_note))
        body.addWidget(self.notice)

        font = QFont(font_family, 15)
        body.addWidget(QLabel("Source text"))
        self.source_view = QPlainTextEdit(session.source)
        self.source_view.setObjectName("source")
        self.source_view.setReadOnly(True)
        self.source_view.setFont(font)
        self.source_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.source_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        body.addWidget(self.source_view, 1)

        body.addWidget(QLabel("Type here"))
        self.entry = ExamEdit()
        self.entry.setFont(font)
        body.addWidget(self.entry, 1)

        self.status = QLabel()
        body.addWidget(self.status)
        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Reset")
        self.new_button = QPushButton("New test")
        self.submit_button = QPushButton("Submit")
        self.submit_button.setObjectName("submit")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.new_button)
        buttons.addStretch()
        buttons.addWidget(self.submit_button)
        body.addLayout(buttons)
        # Buttons must never take focus: a stray Space or Enter while typing would press them.
        for button in (self.start_button, self.reset_button, self.new_button, self.submit_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.entry.key_input.connect(self._on_key)
        self.start_button.clicked.connect(self._on_start)
        self.submit_button.clicked.connect(self._on_submit)
        self.reset_button.clicked.connect(self._on_reset)
        self.new_button.clicked.connect(self.new_test)
        self.clock = QTimer(self)
        self.clock.setInterval(200)
        self.clock.timeout.connect(self._refresh)
        self.clock.start()
        self._refresh()
        self.entry.setFocus()

    def _on_key(self, key) -> None:
        if self.session.key(key):
            self.entry.set_text(self.session.text)
        self._refresh()

    def _on_start(self) -> None:
        self.session.start()
        self.entry.setFocus()
        self._refresh()

    def _on_submit(self) -> None:
        self.session.submit()
        self._refresh()

    def _on_reset(self) -> None:
        self.session.reset()
        self.score_dialog = None
        self.entry.set_text("")
        self.entry.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.entry.setFocus()
        self._refresh()

    def _refresh(self) -> None:
        """Bring every widget in line with the session; the one place that reacts to the clock."""
        self.session.tick()
        self.timer_label.setText(f"Time Remaining: {self.session.timer.display()}")
        phase = self.session.phase
        if phase == READY:
            waiting = "Press Start to begin." if self.session.profile.timer_start == "start_button" else "The clock starts with your first keystroke."
            self.status.setText(waiting)
            self.start_button.setEnabled(True)
        else:
            self.status.setText("Submitted." if phase == FINISHED else "Time is running.")
            self.start_button.setEnabled(False)
        if phase == FINISHED and self.score_dialog is None:
            self._show_score()

    def _show_score(self) -> None:
        self.entry.setEnabled(False)
        self.submit_button.setEnabled(False)
        result = self.session.result
        append_history(
            HistoryEntry.from_result(result, self.session.profile, self.layout_name), self.history_path
        )
        self.score_dialog = ScoreDialog(result, self.session.profile, self.session.source, self.session.text, self)
        self.score_dialog.new_test.connect(self.new_test)
        self.score_dialog.open()
