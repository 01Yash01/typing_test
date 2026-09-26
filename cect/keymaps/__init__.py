"""Keyboard layout tables: physical key + modifier layer -> text.

Layouts are keyed by PS/2 set 1 scan code (what Qt's nativeScanCode() reports on Windows), so they work
whatever layout Windows itself is set to. The tables are JSON files in this package.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from importlib import resources
from typing import Mapping

LAYERS = ("normal", "shift", "altgr", "shift_altgr")
_LAYER_FLAGS = (("normal", False, False), ("shift", True, False), ("altgr", False, True), ("shift_altgr", True, True))


class KeymapError(ValueError):
    """A keymap file is malformed or missing."""


@dataclass(frozen=True)
class Rule:
    """A context rule: if the text before the caret ends with `context`, this key replaces it by `output`."""

    context: str
    scan_code: int
    shift: bool
    altgr: bool
    output: str


@dataclass(frozen=True)
class KeyMap:
    id: str
    name: str
    language: str
    provenance: str
    keys: Mapping[int, Mapping[str, str | None]]  # scan code -> layer -> text (context-free)
    labels: Mapping[int, str]  # scan code -> US-English key cap, for display
    rules: tuple[Rule, ...] = ()

    def translate(self, scan_code: int, shift: bool = False, altgr: bool = False) -> str | None:
        """Context-free text produced by a key in the given modifier state, or None."""
        entry = self.keys.get(scan_code)
        if entry is None:
            return None
        layer = ("shift_altgr" if shift else "altgr") if altgr else ("shift" if shift else "normal")
        return entry[layer]

    @cached_property
    def _rules_by_key(self) -> dict[tuple[int, bool, bool], list[Rule]]:
        """Rules per key, longest context first; equal lengths keep file order (Keyman precedence)."""
        grouped: dict[tuple[int, bool, bool], list[Rule]] = {}
        for rule in self.rules:
            grouped.setdefault((rule.scan_code, rule.shift, rule.altgr), []).append(rule)
        return {key: sorted(rules, key=lambda r: -len(r.context)) for key, rules in grouped.items()}

    @cached_property
    def max_context(self) -> int:
        """How many characters before the caret press() may need to look at."""
        return max((len(r.context) for r in self.rules), default=0)

    def press(self, context: str, scan_code: int, shift: bool = False, altgr: bool = False) -> tuple[int, str] | None:
        """Handle one key press. `context` is the text before the caret.

        Returns (characters to delete before the caret, text to insert), or None if the key does nothing.
        """
        for rule in self._rules_by_key.get((scan_code, shift, altgr), ()):
            if context.endswith(rule.context):
                return len(rule.context), rule.output
        text = self.translate(scan_code, shift, altgr)
        return None if text is None else (0, text)

    @cached_property
    def pressable_keys(self) -> tuple[tuple[int, bool, bool], ...]:
        """Every (scan code, shift, altgr) that can do something, in a stable order."""
        found = {(r.scan_code, r.shift, r.altgr) for r in self.rules}
        for scan, layers in self.keys.items():
            for layer, shift, altgr in _LAYER_FLAGS:
                if layers[layer] is not None:
                    found.add((scan, shift, altgr))
        return tuple(sorted(found))

    @cached_property
    def _reverse(self) -> dict[str, tuple[int, bool, bool]]:
        found: dict[str, tuple[int, bool, bool]] = {}
        for scan in sorted(self.keys):
            for layer, shift, altgr in _LAYER_FLAGS:
                text = self.keys[scan][layer]
                if text is not None and text not in found:
                    found[text] = (scan, shift, altgr)
        return found

    def key_for(self, text: str) -> tuple[int, bool, bool] | None:
        """(scan code, shift, altgr) of the first key that produces exactly `text`."""
        return self._reverse.get(text)

    @cached_property
    def typable_chars(self) -> frozenset[str]:
        """Characters some key or rule can produce (a fast pre-check; typist.plan_keystrokes is exact)."""
        outputs = list(self._reverse) + [r.output for r in self.rules]
        return frozenset(c for text in outputs for c in unicodedata.normalize("NFC", text))

    def missing_chars(self, text: str) -> frozenset[str]:
        """Characters of `text` that no key can produce. Newlines are ignored (Enter is not a layout key)."""
        return frozenset(unicodedata.normalize("NFC", text)) - self.typable_chars - {"\n"}

    @classmethod
    def from_dict(cls, doc: dict) -> "KeyMap":
        try:
            layout_id, name, language, raw_keys = doc["id"], doc["name"], doc["language"], doc["keys"]
        except KeyError as exc:
            raise KeymapError(f"keymap is missing field {exc}") from None
        keys: dict[int, dict[str, str | None]] = {}
        labels: dict[int, str] = {}
        for raw_scan, entry in raw_keys.items():
            try:
                scan = int(raw_scan, 16)
            except (TypeError, ValueError):
                raise KeymapError(f"{layout_id}: scan code {raw_scan!r} is not hexadecimal") from None
            if not 0 < scan < 0x80:
                raise KeymapError(f"{layout_id}: scan code {raw_scan} is outside 0x01-0x7F")
            if scan in keys:
                raise KeymapError(f"{layout_id}: scan code 0x{scan:02X} appears twice")
            unknown = set(entry) - set(LAYERS) - {"label"}
            if unknown:
                raise KeymapError(f"{layout_id}: key {raw_scan} has unknown field(s) {', '.join(sorted(unknown))}")
            layers: dict[str, str | None] = {}
            for layer in LAYERS:
                text = entry.get(layer)
                if text is not None and (not isinstance(text, str) or not text):
                    raise KeymapError(f"{layout_id}: key {raw_scan} layer {layer} must be text or null")
                layers[layer] = text
            keys[scan] = layers
            labels[scan] = str(entry.get("label", ""))
        rules = tuple(cls._parse_rule(layout_id, i, raw) for i, raw in enumerate(doc.get("rules", [])))
        return cls(layout_id, name, language, str(doc.get("provenance", "")), keys, labels, rules)

    @staticmethod
    def _parse_rule(layout_id: str, index: int, raw) -> Rule:
        where = f"{layout_id}: rule {index}"
        if not isinstance(raw, dict) or set(raw) != {"context", "key", "shift", "altgr", "output"}:
            raise KeymapError(f"{where} must have exactly context, key, shift, altgr and output")
        context, output = raw["context"], raw["output"]
        if not isinstance(context, str) or not context or not isinstance(output, str):
            raise KeymapError(f"{where}: context must be non-empty text and output must be text")
        if not isinstance(raw["shift"], bool) or not isinstance(raw["altgr"], bool):
            raise KeymapError(f"{where}: shift and altgr must be true or false")
        try:
            scan = int(raw["key"], 16)
        except (TypeError, ValueError):
            raise KeymapError(f"{where}: key {raw['key']!r} is not hexadecimal") from None
        if not 0 < scan < 0x80:
            raise KeymapError(f"{where}: key {raw['key']} is outside 0x01-0x7F")
        return Rule(context, scan, raw["shift"], raw["altgr"], output)


def available_layouts() -> list[str]:
    return sorted(e.name[: -len(".json")] for e in resources.files(__package__).iterdir() if e.name.endswith(".json"))


def load_keymap(layout_id: str) -> KeyMap:
    if layout_id not in available_layouts():
        raise KeymapError(f"no keymap named {layout_id!r} (available: {', '.join(available_layouts()) or 'none'})")
    text = (resources.files(__package__) / f"{layout_id}.json").read_text(encoding="utf-8")
    return KeyMap.from_dict(json.loads(text))
