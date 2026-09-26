"""Local record of past attempts. Append-only JSON, oldest first, capped so it can't grow forever."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .profile import ExamProfile
from .scoring import ScoreResult

DEFAULT_LIMIT = 200


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    timestamp: float  # epoch seconds
    profile_name: str
    language: str
    layout_name: str
    duration_seconds: int
    net_wpm: float
    gross_wpm: float
    accuracy: float
    passed: bool

    @classmethod
    def from_result(
        cls, result: ScoreResult, profile: ExamProfile, layout_name: str, clock=time.time
    ) -> "HistoryEntry":
        return cls(
            id=uuid.uuid4().hex,
            timestamp=clock(),
            profile_name=profile.name,
            language=profile.language,
            layout_name=layout_name,
            duration_seconds=profile.duration_seconds,
            net_wpm=result.net_wpm,
            gross_wpm=result.gross_wpm,
            accuracy=result.accuracy,
            passed=result.passed,
        )


def history_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "cect" / "history.json"


def load_history(path: Path | None = None) -> list[HistoryEntry]:
    try:
        raw = json.loads((path or history_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        try:
            entries.append(HistoryEntry(**item))
        except TypeError:
            continue  # one malformed row must not lose the rest of the history
    return entries


def append_history(entry: HistoryEntry, path: Path | None = None, limit: int = DEFAULT_LIMIT) -> None:
    target = path or history_path()
    entries = load_history(target)[-(limit - 1):] + [entry]
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # history is a convenience; losing it must not stop an exam
