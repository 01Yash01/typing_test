"""Exam rules as data: one JSON profile per exam variant, validated on load."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path

LANGUAGES = ("hindi", "english")
TIMER_STARTS = ("first_keystroke", "start_button")
SCORING_MODES = ("keystroke", "word")


class ProfileError(ValueError):
    """A profile file is malformed."""


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class ExamProfile:
    name: str
    language: str
    duration_seconds: int
    timer_start: str
    backspace_allowed: bool
    scoring: str
    min_net_wpm: float
    min_accuracy: float
    notes: str = ""

    def __post_init__(self):
        def fail(message):
            raise ProfileError(f"profile {self.name!r}: {message}")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ProfileError("profile name must be a non-empty string")
        for field, allowed in (("language", LANGUAGES), ("timer_start", TIMER_STARTS), ("scoring", SCORING_MODES)):
            if getattr(self, field) not in allowed:
                fail(f"{field} must be one of {', '.join(allowed)} (got {getattr(self, field)!r})")
        if isinstance(self.duration_seconds, bool) or not isinstance(self.duration_seconds, int) or self.duration_seconds <= 0:
            fail("duration_seconds must be a positive whole number")
        if not isinstance(self.backspace_allowed, bool):
            fail("backspace_allowed must be true or false")
        if not _is_number(self.min_net_wpm) or self.min_net_wpm < 0:
            fail("min_net_wpm must be a number >= 0")
        if not _is_number(self.min_accuracy) or not 0 <= self.min_accuracy <= 100:
            fail("min_accuracy must be a number between 0 and 100")
        if not isinstance(self.notes, str):
            fail("notes must be a string")

    @classmethod
    def from_dict(cls, data: dict) -> "ExamProfile":
        fields = set(cls.__dataclass_fields__)
        unknown = set(data) - fields
        if unknown:
            raise ProfileError(f"unknown profile field(s): {', '.join(sorted(unknown))}")
        missing = fields - set(data) - {"notes"}
        if missing:
            raise ProfileError(f"missing profile field(s): {', '.join(sorted(missing))}")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


def load_profile(path: str | Path) -> ExamProfile:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"{path}: expected a JSON object")
    try:
        return ExamProfile.from_dict(data)
    except ProfileError as exc:
        raise ProfileError(f"{path}: {exc}") from exc


def builtin_profiles() -> dict[str, ExamProfile]:
    """The profiles shipped inside the package, keyed by file name without extension."""
    found = {}
    for entry in sorted(resources.files("cect.profiles").iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".json"):
            with resources.as_file(entry) as path:
                found[entry.name[: -len(".json")]] = load_profile(path)
    return found
