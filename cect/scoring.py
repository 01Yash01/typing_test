"""Typing-test scoring: CPCT-style speed and accuracy, plus the text alignment behind them.

The submitted text is aligned to the source word by word (minimum edit distance), so one skipped or
extra character costs only that character. (Comparing position by position would misalign everything
after the first slip.)

  keystroke mode  credit is per character: inside a word that differs from the source, the characters
                  that still match in order are credited.
  word mode       credit is per word: a word earns its keystrokes only when typed exactly right.

In both modes 5 keystrokes (spaces included) = 1 word, and

  gross WPM = total keystrokes / 5 / minutes
  net WPM   = credited keystrokes / 5 / minutes
  accuracy  = credited / (credited + mistakes) * 100

A mistake is a wrong, missing or extra character (word mode: word); a substitution counts once. Source
text after the point where the candidate stopped is not held against them. Results are rounded to two
decimals and pass/fail is judged on the rounded values, so the scorecard never contradicts itself.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import NamedTuple

from .profile import ExamProfile

WORD_KEYSTROKES = 5
_WORD_RE = re.compile(r"\S+\s*")


def normalize(text: str) -> str:
    """Unify line endings and Unicode form so equivalent Devanagari spellings compare equal."""
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def split_words(text: str) -> list[str]:
    """Split into words that each carry their trailing whitespace; leading whitespace is dropped."""
    return _WORD_RE.findall(text)


def lcs_info(a: str, b: str) -> tuple[int, int]:
    """Return (length of the longest common subsequence, shortest prefix of `a` that achieves it).

    Bit-parallel LCS (Crochemore et al. 2001, Hyyro 2004): bit i of V stays 1 until position i of `a`
    raises the LCS of a[:i+1] against the part of `b` consumed so far, so the zero bits mark exactly
    where the prefix LCS grows.
    """
    n = len(a)
    if n == 0 or not b:
        return 0, 0
    masks: dict[str, int] = {}
    for i, ch in enumerate(a):
        masks[ch] = masks.get(ch, 0) | (1 << i)
    full = (1 << n) - 1
    v = full
    for ch in b:
        m = masks.get(ch)
        if m is None:
            continue
        u = v & m
        v = ((v + u) | (v - u)) & full  # (V + (V & M)) | (V & ~M)
    zeros = ~v & full
    return zeros.bit_count(), zeros.bit_length()


class _Counts(NamedTuple):
    correct_units: int  # characters (keystroke mode) or words (word mode)
    credited_keystrokes: int
    mistakes: int


_DIAG, _DEL, _INS = 0, 1, 2


def _align(src: list[str], typed: list[str]) -> list[tuple[str, int, int, int, int]]:
    """Align two word lists by edit distance; return difflib-style (tag, i1, i2, j1, j2) opcodes.

    Minimising the number of wrong, missing and extra words keeps repetitive text (drills, repeated
    words) aligned correctly, and stops a stray word from being paired with an identical word far
    ahead, which greedy longest-run matching (difflib) gets wrong. Source words after the last typed
    word cost nothing and are left out of the result: the candidate simply never reached them.
    """
    n, m = len(src), len(typed)
    p = 0  # an identical prefix is always part of an optimal alignment
    while p < n and p < m and src[p] == typed[p]:
        p += 1
    ops: list[tuple[str, int, int, int, int]] = [("equal", 0, p, 0, p)] if p else []
    rows, cols = n - p, m - p

    ptr = [bytearray(cols + 1) for _ in range(rows + 1)]
    for j in range(1, cols + 1):
        ptr[0][j] = _INS
    prev = list(range(cols + 1))
    end_cost = [cols] + [0] * rows  # cost of aligning the first i source words to all typed words
    for i in range(1, rows + 1):
        ptr[i][0] = _DEL
        cur = [i] + [0] * cols
        word, row = src[p + i - 1], ptr[i]
        for j in range(1, cols + 1):
            diag = prev[j - 1] + (word != typed[p + j - 1])
            dele = prev[j] + 1
            ins = cur[j - 1] + 1
            if diag <= dele and diag <= ins:
                cur[j], row[j] = diag, _DIAG
            elif dele <= ins:
                cur[j], row[j] = dele, _DEL
            else:
                cur[j], row[j] = ins, _INS
        end_cost[i] = cur[cols]
        prev = cur

    end_i, best = 0, end_cost[0]
    for i in range(1, rows + 1):
        if end_cost[i] <= best:  # on a tie prefer covering more source: a slip beats an omission
            end_i, best = i, end_cost[i]

    steps = []
    i, j = end_i, cols
    while i or j:
        move = ptr[i][j]
        if move == _DIAG:
            steps.append(src[p + i - 1] == typed[p + j - 1])
            i, j = i - 1, j - 1
        elif move == _DEL:
            steps.append("D")
            i -= 1
        else:
            steps.append("I")
            j -= 1
    steps.reverse()

    si = sj = p  # absolute positions; group runs of matches and runs of everything else
    run_start = (si, sj)
    run_is_match = None

    def flush():
        if run_is_match is None:
            return
        (i1, j1), (i2, j2) = run_start, (si, sj)
        if run_is_match:
            if ops and ops[-1][0] == "equal":
                ops[-1] = ("equal", ops[-1][1], i2, ops[-1][3], j2)
            else:
                ops.append(("equal", i1, i2, j1, j2))
        else:
            ops.append(("replace" if i2 > i1 and j2 > j1 else "delete" if i2 > i1 else "insert", i1, i2, j1, j2))

    for step in steps:
        is_match = step is True
        if is_match != run_is_match:
            flush()
            run_start, run_is_match = (si, sj), is_match
        if step == "D":
            si += 1
        elif step == "I":
            sj += 1
        else:
            si, sj = si + 1, sj + 1
    flush()
    return ops


def _opcodes(src_tokens: list[str], typed_tokens: list[str]):
    return _align([t.rstrip() for t in src_tokens], [t.rstrip() for t in typed_tokens])


def _keystroke_counts(src_tokens: list[str], typed_tokens: list[str]) -> _Counts:
    ops = _opcodes(src_tokens, typed_tokens)
    correct = mistakes = 0
    for n, (tag, i1, i2, j1, j2) in enumerate(ops):
        last = n == len(ops) - 1
        src = "".join(src_tokens[i1:i2])
        typed = "".join(typed_tokens[j1:j2])
        matched, span = (len(src), len(src)) if src == typed else lcs_info(src, typed)
        if not last:
            span = len(src)  # only the final region can be cut short by running out of time
        correct += matched
        mistakes += max(span - matched, len(typed) - matched)
    return _Counts(correct, correct, mistakes)


def _word_counts(src_tokens: list[str], typed_tokens: list[str]) -> _Counts:
    ops = _opcodes(src_tokens, typed_tokens)
    words = credited = mistakes = 0
    for n, (tag, i1, i2, j1, j2) in enumerate(ops):
        last = n == len(ops) - 1
        if tag == "equal":
            words += i2 - i1
            for s, t in zip(src_tokens[i1:i2], typed_tokens[j1:j2]):
                word = len(s.rstrip())
                credited += word + min(len(s) - word, len(t) - len(t.rstrip()))
        elif last:
            mistakes += j2 - j1  # judge the final region only on what was typed
        else:
            mistakes += max(i2 - i1, j2 - j1)
    return _Counts(words, credited, mistakes)


@dataclass(frozen=True)
class WordDiff:
    """One word's outcome when the typed text is compared to the source, word by word.

    Always a word-level comparison, regardless of the exam's scoring mode: it is what a candidate
    reviews after the test, not what decides the pass mark. Built from the same alignment `score` uses,
    so the count of non-"correct" entries always equals `ScoreResult.mistakes` under word-mode scoring.
    """

    status: str  # "correct", "wrong", "missing" (never typed) or "extra" (typed beyond the source)
    source: str  # the source word, or "" for "extra"
    typed: str  # what was typed, or "" for "missing"


def word_diff(source: str, typed: str) -> list[WordDiff]:
    """Word-by-word comparison of `typed` against `source`, for a post-exam mistake review."""
    src_tokens = [w.rstrip() for w in split_words(normalize(source))]
    if not src_tokens:
        raise ValueError("source text is empty")
    typed_tokens = [w.rstrip() for w in split_words(normalize(typed))]
    ops = _align(src_tokens, typed_tokens)

    diffs: list[WordDiff] = []
    for n, (tag, i1, i2, j1, j2) in enumerate(ops):
        src_words, typed_words = src_tokens[i1:i2], typed_tokens[j1:j2]
        if tag == "equal":
            diffs.extend(WordDiff("correct", s, t) for s, t in zip(src_words, typed_words))
        elif n == len(ops) - 1 and tag == "delete":
            continue  # source the candidate never reached: not a mistake, not shown
        elif n == len(ops) - 1:
            # Matches score()'s final-region rule: only what was typed counts, so a candidate who ran
            # out of time is not also penalised for the untyped words beyond it.
            for k, t in enumerate(typed_words):
                s = src_words[k] if k < len(src_words) else ""
                diffs.append(WordDiff("wrong" if s else "extra", s, t))
        else:
            for k in range(max(len(src_words), len(typed_words))):
                s = src_words[k] if k < len(src_words) else ""
                t = typed_words[k] if k < len(typed_words) else ""
                diffs.append(WordDiff("wrong" if s and t else "missing" if s else "extra", s, t))
    return diffs


@dataclass(frozen=True)
class ScoreResult:
    total_keystrokes: int
    correct_keystrokes: int
    mistakes: int
    mistake_unit: str  # "keystrokes" or "words", following the scoring mode
    elapsed_seconds: float
    gross_wpm: float
    net_wpm: float
    accuracy: float  # percent
    passed: bool


def score(
    source: str,
    typed: str,
    elapsed_seconds: float,
    profile: ExamProfile,
    key_presses: int | None = None,
) -> ScoreResult:
    """Score `typed` against `source`.

    `key_presses`, when the UI counted real key depressions (backspaces included), replaces the length
    of the submitted text as the total-keystroke figure used for gross speed.
    """
    src_tokens = split_words(normalize(source))
    if not src_tokens:
        raise ValueError("source text is empty")
    typed = normalize(typed)
    typed_tokens = split_words(typed)

    counter = _keystroke_counts if profile.scoring == "keystroke" else _word_counts
    counts = counter(src_tokens, typed_tokens)

    total = len(typed) if key_presses is None else key_presses
    minutes = elapsed_seconds / 60

    def per_minute(keystrokes: int) -> float:
        return round(keystrokes / WORD_KEYSTROKES / minutes, 2) if minutes > 0 else 0.0

    denominator = counts.correct_units + counts.mistakes
    accuracy = round(counts.correct_units / denominator * 100, 2) if denominator else 0.0
    gross, net = per_minute(total), per_minute(counts.credited_keystrokes)
    return ScoreResult(
        total_keystrokes=total,
        correct_keystrokes=counts.credited_keystrokes,
        mistakes=counts.mistakes,
        mistake_unit="keystrokes" if profile.scoring == "keystroke" else "words",
        elapsed_seconds=elapsed_seconds,
        gross_wpm=gross,
        net_wpm=net,
        accuracy=accuracy,
        passed=net >= profile.min_net_wpm and accuracy >= profile.min_accuracy,
    )
