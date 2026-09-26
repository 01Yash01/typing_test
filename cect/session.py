"""One sitting of the exam: typed text, countdown and result. No GUI code, so it is fully testable."""
from __future__ import annotations

import time
from typing import Callable

from .entry import EntryPolicy, KeyInput
from .keymaps import KeyMap
from .profile import ExamProfile
from .scoring import ScoreResult, score
from .timer import ExamTimer

READY, RUNNING, FINISHED = "ready", "running", "finished"


class ExamSession:
    def __init__(
        self,
        profile: ExamProfile,
        source: str,
        keymap: KeyMap | None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.profile = profile
        self.source = source
        self.timer = ExamTimer(profile.duration_seconds, clock)
        self.policy = EntryPolicy(keymap, profile.backspace_allowed, allow_newline="\n" in source)
        self.text = ""
        self.key_presses = 0
        self.result: ScoreResult | None = None

    @property
    def phase(self) -> str:
        if self.result is not None:
            return FINISHED
        return RUNNING if self.timer.started else READY

    def start(self) -> None:
        """Begin the countdown (the Start button; with first_keystroke timing typing does this itself)."""
        if self.phase == READY:
            self.timer.start()

    def key(self, key: KeyInput) -> bool:
        """Feed one key press. Returns True if the typed text changed."""
        self._finish_if_expired()
        if self.phase == FINISHED:
            return False
        if self.phase == READY and self.profile.timer_start == "start_button":
            return False
        edit = self.policy.handle(self.text, key)
        if edit is None:
            return False
        self.timer.start()
        delete, insert = edit
        self.text = self.text[: len(self.text) - delete] + insert
        self.key_presses += 1
        return True

    def tick(self) -> bool:
        """Call regularly from the GUI. Returns True on the tick that ends the exam because time ran out."""
        return self._finish_if_expired()

    def submit(self) -> ScoreResult:
        """End the exam and score it. Safe to call again: the first result stands."""
        if self.result is None:
            self.timer.stop()  # a no-op once time has run out: elapsed is already clamped to the duration
            self.result = score(self.source, self.text, self.timer.elapsed, self.profile)
        return self.result

    def reset(self, source: str | None = None) -> None:
        if source is not None:
            self.source = source
            self.policy.allow_newline = "\n" in source
        self.timer.reset()
        self.text = ""
        self.key_presses = 0
        self.result = None

    def _finish_if_expired(self) -> bool:
        if self.result is None and self.timer.expired:
            self.submit()
            return True
        return False
