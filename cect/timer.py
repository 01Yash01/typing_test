"""Exam countdown driven by a monotonic clock.

The timer is polled, never scheduled: the UI owns one repeating tick and reads `remaining` from it.
Because it holds no callbacks, a reset followed by a quick restart cannot leave two countdowns
running, and elapsed time is clamped to the exam duration rather than drifting past it.
"""
from __future__ import annotations

import math
import time
from typing import Callable


class ExamTimer:
    def __init__(self, duration_seconds: float, clock: Callable[[], float] = time.monotonic):
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self.duration = float(duration_seconds)
        self._clock = clock
        self._started_at: float | None = None
        self._stopped_at: float | None = None

    def start(self) -> None:
        """Begin counting. Does nothing if already started, until reset() is called."""
        if self._started_at is None:
            self._started_at = self._clock()

    def stop(self) -> None:
        """Freeze elapsed time (e.g. on Submit). Does nothing unless the timer is running."""
        if self.running:
            self._stopped_at = self._clock()

    def reset(self) -> None:
        self._started_at = None
        self._stopped_at = None

    @property
    def started(self) -> bool:
        return self._started_at is not None

    @property
    def elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        end = self._stopped_at if self._stopped_at is not None else self._clock()
        return min(max(end - self._started_at, 0.0), self.duration)

    @property
    def remaining(self) -> float:
        return self.duration - self.elapsed

    @property
    def expired(self) -> bool:
        return self.started and self._stopped_at is None and self.elapsed >= self.duration

    @property
    def running(self) -> bool:
        return self.started and self._stopped_at is None and not self.expired

    @property
    def finished(self) -> bool:
        return self.started and not self.running

    def display(self) -> str:
        """MM:SS, rounded up so the clock reads 00:00 only once time has really run out."""
        minutes, seconds = divmod(math.ceil(self.remaining), 60)
        return f"{minutes:02d}:{seconds:02d}"
