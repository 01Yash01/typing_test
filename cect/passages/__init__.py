"""Passage bank: practice texts per language, stored as JSON in this package."""
from __future__ import annotations

import json
import random
import unicodedata
from dataclasses import dataclass
from importlib import resources


class PassageError(ValueError):
    """A passage file is malformed."""


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    language: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def load_passages(language: str) -> list[Passage]:
    path = resources.files(__package__) / f"{language}.json"
    if not path.is_file():
        raise PassageError(f"no passages for language {language!r}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    passages, seen = [], set()
    for raw in doc.get("passages", []):
        try:
            pid, title, text = raw["id"], raw["title"], raw["text"]
        except KeyError as exc:
            raise PassageError(f"{language}.json: a passage is missing {exc}") from None
        if pid in seen:
            raise PassageError(f"{language}.json: duplicate passage id {pid!r}")
        seen.add(pid)
        passages.append(Passage(pid, title, language, unicodedata.normalize("NFC", text.strip())))
    if not passages:
        raise PassageError(f"{language}.json contains no passages")
    return passages


def build_source(
    passages: list[Passage],
    passage_id: str | None,
    minutes: float,
    target_wpm: float,
    rng: random.Random | None = None,
) -> str:
    """The text to show for one test.

    A chosen passage is used as it is. Otherwise passages are drawn at random and joined until there
    are enough words to keep a typist at `target_wpm` busy for `minutes`, reusing passages if the bank
    is small.
    """
    if passage_id is not None:
        return next(p for p in passages if p.id == passage_id).text
    rng = rng or random.Random()
    needed = max(1, round(minutes * target_wpm))
    pool: list[Passage] = []
    parts: list[str] = []
    words = 0
    while words < needed:
        if not pool:
            pool = passages[:]
            rng.shuffle(pool)
        chosen = pool.pop()
        parts.append(chosen.text)
        words += chosen.word_count
    return " ".join(parts)
