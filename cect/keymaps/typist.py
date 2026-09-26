"""A virtual typist: works out which key presses produce a given text on a layout.

Used to prove a layout can type real passages (context rules included) and to drive the exam UI in
tests with genuine scan codes. Not needed at exam time.
"""
from __future__ import annotations

import unicodedata

from . import KeyMap

Key = tuple[int, bool, bool]  # (scan code, shift, altgr)

# Keyman emits the precomposed nukta letters U+0958-U+095F, which NFC splits into base + nukta. Splitting
# them with a plain character table is all the planner needs, and is far cheaper than normalising text
# for every candidate key.
_EXCLUDED = {
    0x0958: "क़", 0x0959: "ख़", 0x095A: "ग़", 0x095B: "ज़",
    0x095C: "ड़", 0x095D: "ढ़", 0x095E: "फ़", 0x095F: "य़",
}


def _canon(text: str) -> str:
    return text.translate(_EXCLUDED)


def apply_key(keymap: KeyMap, text: str, key: Key) -> str:
    """Text after pressing `key` at the end of `text` (append-only, as in the exam entry pane)."""
    tail = text[-keymap.max_context:] if keymap.max_context else ""
    edit = keymap.press(tail, *key)
    if edit is None:
        return text
    delete, insert = edit
    return text[: len(text) - delete] + insert


def type_keys(keymap: KeyMap, keys: list[Key]) -> str:
    text = ""
    for key in keys:
        text = apply_key(keymap, text, key)
    return text


def plan_keystrokes(keymap: KeyMap, target: str, max_depth: int = 3) -> list[Key] | None:
    """Key presses that make the layout produce exactly `target`, or None if it can't be typed.

    Works left to right. From the text typed so far it takes the single press that extends it furthest
    while staying a prefix of the target. Some characters need a short run of presses whose
    intermediate text is not a prefix (ओ is अ, then the aa-matra key making आ, then a matra key), so
    when no single press works it searches runs of up to `max_depth`, using only keys that can help
    build the next few characters.
    """
    target = unicodedata.normalize("NFC", target)
    all_keys = list(keymap.pressable_keys)
    outputs = {key: _outputs(keymap, key) for key in all_keys}
    typed = ""  # raw text as the layout produced it (rule contexts match against this)
    plan: list[Key] = []
    while _canon(typed) != target:
        step = _extend(keymap, typed, target, all_keys, outputs, max_depth)
        if step is None:
            return None
        plan.extend(step)
        for key in step:
            typed = apply_key(keymap, typed, key)
    return plan


def _outputs(keymap: KeyMap, key: Key) -> set[str]:
    chars: set[str] = set()
    text = keymap.translate(*key)
    if text:
        chars.update(text)
    for rule in keymap._rules_by_key.get(key, ()):
        chars.update(rule.output)
    return chars


def _focus(keymap: KeyMap, all_keys, outputs, wanted: str) -> list[Key]:
    """Keys that can help produce `wanted`: keys typing its characters, and keys triggering a rule that
    does, following rule chains (ओ comes from आ, which comes from अ)."""
    relevant, triggers = set(wanted), set()
    changed = True
    while changed:
        changed = False
        for rule in keymap.rules:
            if set(rule.output) & relevant:
                triggers.add((rule.scan_code, rule.shift, rule.altgr))
                if not set(rule.context) <= relevant:
                    relevant |= set(rule.context)
                    changed = True
    return [k for k in all_keys if k in triggers or outputs[k] & relevant]


def _extend(keymap, typed, target, all_keys, outputs, max_depth):
    # Only the last few characters can change (a rule replaces at most max_context characters per press),
    # so candidates are judged on that short tail; the settled head is already a prefix of the target.
    reach = (keymap.max_context + 1) * max_depth
    split = max(0, len(typed) - reach)
    head_len = len(_canon(typed[:split]))  # canon maps characters one by one, so lengths add up
    tail = typed[split:]
    done = head_len + len(_canon(tail))

    def better(text):
        text = _canon(text)
        return head_len + len(text) > done and target.startswith(text, head_len)

    best, best_gain = None, 0
    for key in all_keys:  # one press: take the longest gain
        text = apply_key(keymap, tail, key)
        if better(text) and len(_canon(text)) > best_gain:
            best, best_gain = [key], len(_canon(text))
    if best:
        return best

    focused = _focus(keymap, all_keys, outputs, target[done: done + 3])

    def search(text, depth, path, seen):
        if depth == 0:
            return None
        for key in focused:
            nxt = apply_key(keymap, text, key)
            if nxt == text:
                continue
            if better(nxt):
                return path + [key]
            state = (nxt[-max(keymap.max_context, 1) - 1:], depth - 1)
            if state in seen:
                continue
            seen.add(state)
            found = search(nxt, depth - 1, path + [key], seen)
            if found:
                return found
        return None

    return search(tail, max_depth, [], set())
