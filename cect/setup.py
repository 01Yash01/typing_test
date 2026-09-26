"""What the candidate chooses before an exam, and how those choices become an ExamSession. No GUI code."""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .keymaps import available_layouts, load_keymap
from .passages import build_source, load_passages
from .profile import ExamProfile
from .session import ExamSession

# (seconds, label); None means "use the exam profile's own duration".
DURATIONS = (
    (None, "Exam default"),
    (60, "1 minute (practice)"),
    (120, "2 minutes (practice)"),
    (300, "5 minutes (practice)"),
    (900, "15 minutes"),
)
SYSTEM_KEYBOARD = "System keyboard (English)"
PREFERRED_FIRST = "remington_gail_hindi"  # the layout the exam uses, so it is the default


@dataclass(frozen=True)
class SetupChoice:
    profile_id: str
    layout_id: str | None  # None: the system keyboard (English)
    duration_seconds: int | None  # None: the profile's default
    backspace_allowed: bool
    passage_id: str | None  # None: random passages long enough for the time


def layouts_for(language: str) -> list[tuple[str | None, str]]:
    """(layout id, display name) choices for a language; the exam's own layout comes first."""
    if language != "hindi":
        return [(None, SYSTEM_KEYBOARD)]
    found = [(km.id, km.name) for km in map(load_keymap, available_layouts()) if km.language == language]
    return sorted(found, key=lambda item: (item[0] != PREFERRED_FIRST, item[1]))


def effective_profile(profile: ExamProfile, choice: SetupChoice) -> ExamProfile:
    return replace(
        profile,
        duration_seconds=choice.duration_seconds or profile.duration_seconds,
        backspace_allowed=choice.backspace_allowed,
    )


def build_session(
    profile: ExamProfile, choice: SetupChoice, rng: random.Random | None = None
) -> tuple[ExamSession, str]:
    """Return the session for these choices and the name of the keyboard layout in use."""
    profile = effective_profile(profile, choice)
    keymap = load_keymap(choice.layout_id) if choice.layout_id else None
    passages = load_passages(profile.language)
    target_wpm = max(30.0, profile.min_net_wpm * 2)  # enough text that a good typist doesn't run out
    source = build_source(passages, choice.passage_id, profile.duration_seconds / 60, target_wpm, rng)
    return ExamSession(profile, source, keymap), (keymap.name if keymap else SYSTEM_KEYBOARD)
