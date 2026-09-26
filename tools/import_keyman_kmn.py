"""Convert a Keyman .kmn keyboard into a cect keymap JSON file.

Handles the subset of the Keyman language used by SIL's "Remington GAIL": stores (quoted strings,
U+XXXX values and ranges, key names), `any()` / `index()` / `context`, and key rules with or without
input context. `any()` classes are expanded into concrete rules, so the runtime needs no Keyman
interpreter. Anything it does not understand is an error, never silently skipped.

Rule precedence follows Keyman: among the rules for a key, the one with the longest matching input
context wins (the runtime sorts by context length).

Example:
    python tools/import_keyman_kmn.py remington_gail.kmn --id remington_gail_hindi \
        --name "Hindi Remington GAIL (Keyman, SIL Global)" --language hindi \
        --source-url https://github.com/keymanapp/keyboards/blob/<commit>/release/r/remington_gail/source/remington_gail.kmn \
        --license "MIT, Copyright (c) 2022-2026 SIL Global" --out cect/keymaps/remington_gail_hindi.json
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Keyman virtual key name -> PS/2 set 1 scan code (main alphanumeric block of a US keyboard).
VK_SCAN = {"K_SPACE": 0x39, "K_HYPHEN": 0x0C, "K_EQUAL": 0x0D, "K_LBRKT": 0x1A, "K_RBRKT": 0x1B,
           "K_COLON": 0x27, "K_QUOTE": 0x28, "K_BKQUOTE": 0x29, "K_BKSLASH": 0x2B,
           "K_COMMA": 0x33, "K_PERIOD": 0x34, "K_SLASH": 0x35}
for _i, _c in enumerate("1234567890"):
    VK_SCAN[f"K_{_c}"] = 0x02 + _i
for _row, _base in (("QWERTYUIOP", 0x10), ("ASDFGHJKL", 0x1E), ("ZXCVBNM", 0x2C)):
    for _i, _c in enumerate(_row):
        VK_SCAN[f"K_{_c}"] = _base + _i

# US-English key caps: character -> (scan code, shift)
_UNSHIFTED = "1234567890-=qwertyuiop[]asdfghjkl;'`\\zxcvbnm,./"
_SCANS = list(range(0x02, 0x0E)) + list(range(0x10, 0x1C)) + list(range(0x1E, 0x29)) + [0x29, 0x2B] + list(range(0x2C, 0x36))
US_CHAR = {c: (s, False) for c, s in zip(_UNSHIFTED, _SCANS)}
US_CHAR.update({c.upper(): (s, True) for c, (s, _) in list(US_CHAR.items()) if c.isalpha()})
_US_SHIFTED = "~!@#$%^&*()_+{}|:\"<>?"
_US_BASE_OF_SHIFTED = "`1234567890-=[]\\;',./"
US_CHAR.update({s: (US_CHAR[u][0], True) for s, u in zip(_US_SHIFTED, _US_BASE_OF_SHIFTED)})
US_CHAR[" "] = (0x39, False)
SCAN_LABEL = {s: c for c, (s, sh) in US_CHAR.items() if not sh and not c.isupper()}

ALLOWED = (
    lambda ch: 0x0900 <= ord(ch) <= 0x097F or 0x20 <= ord(ch) <= 0x7E or ch in "‌‍‘’“”×÷"
)

TOKEN = re.compile(
    r"""\s+|"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|U\+(?P<u>[0-9A-Fa-f]{4,6})|\[(?P<key>[^\]]+)\]
        |any\((?P<any>\w+)\)|index\((?P<idx>\w+)\s*,\s*(?P<n>\d+)\)|(?P<ctx>\bcontext\b)|(?P<range>\.\.)|(?P<plus>\+)|(?P<gt>>)""",
    re.X,
)


_KINDS = ("dq", "sq", "u", "key", "any", "idx", "ctx", "range", "plus", "gt")


def kind_of(match):
    """Which top-level alternative matched (None for whitespace)."""
    return next((k for k in _KINDS if match.group(k) is not None), None)


def strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "c" and (i == 0 or line[i - 1].isspace()) and (i + 1 == len(line) or line[i + 1].isspace()):
            return line[:i]
    return line


def logical_lines(text):
    out, buf = [], ""
    for raw in text.splitlines():
        line = strip_comment(raw).rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        out.append((buf + line).strip())
        buf = ""
    return [line for line in out if line]


def parse_key(spec):
    """'SHIFT RALT K_A' -> (scan, shift, altgr), or None for keys this converter does not model."""
    parts = spec.split()
    name, mods = parts[-1], set(parts[:-1])
    if mods - {"SHIFT", "RALT"} or name not in VK_SCAN:
        return None  # CAPS/NCAPS variants and the numeric keypad are not part of the main block
    return (VK_SCAN[name], "SHIFT" in mods, "RALT" in mods)


def items(tokens, where):
    """Turn regex matches into elements; ('range') operators are folded into their neighbours."""
    out = []
    for m in tokens:
        kind = kind_of(m)
        if kind is None:
            continue
        if kind in ("dq", "sq"):
            out.extend(("char", ch) for ch in m.group(kind))
        elif kind == "u":
            out.append(("char", chr(int(m.group("u"), 16))))
        elif kind == "key":
            out.append(("key", parse_key(m.group("key")), m.group("key")))
        elif kind == "any":
            out.append(("any", m.group("any")))
        elif kind == "idx":
            out.append(("index", m.group("idx"), int(m.group("n"))))
        elif kind == "ctx":
            out.append(("context",))
        elif kind == "range":
            out.append(("range",))
        else:
            out.append((kind,))
    folded, i = [], 0
    while i < len(out):
        if i + 2 < len(out) and out[i + 1] == ("range",):
            a, b = out[i], out[i + 2]
            if a[0] == "char" and b[0] == "char":
                folded.extend(("char", chr(c)) for c in range(ord(a[1]), ord(b[1]) + 1))
            elif a[0] == "key" and b[0] == "key":
                m1, m2 = re.search(r"K_(\D*)(\d)$", a[2]), re.search(r"K_(\D*)(\d)$", b[2])
                if not (m1 and m2 and m1.group(1) == m2.group(1)):
                    raise SystemExit(f"{where}: unsupported key range {a[2]} .. {b[2]}")
                for d in range(int(m1.group(2)), int(m2.group(2)) + 1):
                    spec = re.sub(r"K_(\D*)\d$", lambda mm: f"K_{mm.group(1)}{d}", a[2])
                    folded.append(("key", parse_key(spec), spec))
            else:
                raise SystemExit(f"{where}: unsupported range")
            i += 3
        else:
            folded.append(out[i])
            i += 1
    return folded


def tokenize(text):
    pos, tokens = 0, []
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise SystemExit(f"cannot tokenize near: {text[pos:pos + 30]!r}")
        tokens.append(m)
        pos = m.end()
    return tokens


def as_key(element, where):
    """A store element used on the key side: key names as-is, characters as their US key cap."""
    if element[0] == "key":
        return element[1]
    if element[0] == "char" and element[1] in US_CHAR:
        scan, shift = US_CHAR[element[1]]
        return (scan, shift, False)
    raise SystemExit(f"{where}: cannot use {element!r} as a key")


def convert(kmn_text):
    stores, rules_src = {}, []
    for line in logical_lines(kmn_text):
        m = re.match(r"store\((\w+|&\w+)\)\s*(.*)$", line)
        if m:
            if not m.group(1).startswith("&"):
                stores[m.group(1)] = items(tokenize(m.group(2)), f"store {m.group(1)}")
            continue
        if line.startswith(("begin", "group(")):
            continue
        rules_src.append(line)

    keys, rules, skipped = {}, [], 0
    for line in rules_src:
        tokens = tokenize(line)
        kinds = [kind_of(t) for t in tokens]
        if "gt" not in kinds or "plus" not in kinds:
            raise SystemExit(f"unrecognised statement: {line}")
        gt = kinds.index("gt")
        lhs, rhs = tokens[:gt], tokens[gt + 1:]
        plus = [kind_of(t) for t in lhs].index("plus")
        ctx, keyi = items(lhs[:plus], line), items(lhs[plus + 1:], line)
        out = items(rhs, line)
        if len(keyi) != 1:
            raise SystemExit(f"rule needs exactly one key: {line}")
        elements = ctx + keyi
        anys = [i for i, e in enumerate(elements) if e[0] == "any"]
        if len(anys) > 1:
            raise SystemExit(f"more than one any() in a rule is not supported: {line}")
        count = len(stores[elements[anys[0]][1]]) if anys else 1
        for k in range(count):
            concrete = []
            for e in elements:
                concrete.append(stores[e[1]][k] if e[0] == "any" else e)
            key = as_key(concrete[-1], line)
            context = "".join(e[1] for e in concrete[:-1]) if all(e[0] == "char" for e in concrete[:-1]) else None
            if context is None:
                raise SystemExit(f"non-character context: {line}")
            text = ""
            for o in out:
                if o[0] == "char":
                    text += o[1]
                elif o[0] == "context":
                    text += context
                elif o[0] == "index":
                    if not anys or o[2] - 1 != anys[0]:
                        raise SystemExit(f"index() must refer to the rule's any() position: {line}")
                    text += stores[o[1]][k][1]
                else:
                    raise SystemExit(f"unsupported output element {o!r}: {line}")
            if key is None:
                skipped += 1
                continue
            scan, shift, altgr = key
            bad = [ch for ch in text if not ALLOWED(ch)]
            if bad:
                raise SystemExit(f"output outside the allowed character set {bad!r}: {line}")
            if context:
                rules.append({"context": context, "key": f"0x{scan:02X}", "shift": shift, "altgr": altgr, "output": text})
            else:
                layer = ("shift_altgr" if shift else "altgr") if altgr else ("shift" if shift else "normal")
                slot = keys.setdefault(scan, {})
                if layer in slot and slot[layer] != text:
                    raise SystemExit(f"conflicting rules for key 0x{scan:02X} {layer}: {slot[layer]!r} vs {text!r}")
                slot[layer] = text
    keys.setdefault(0x39, {})["normal"] = " "  # the space bar passes through unchanged
    return keys, rules, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kmn")
    for name in ("id", "name", "language", "source_url", "license", "out"):
        parser.add_argument(f"--{name.replace('_', '-')}", required=True)
    args = parser.parse_args()

    raw = Path(args.kmn).read_bytes()
    keys, rules, skipped = convert(raw.decode("utf-8"))
    version = re.search(r"store\(&KEYBOARDVERSION\)\s*'([^']+)'", raw.decode("utf-8"))
    doc = {
        "id": args.id,
        "name": args.name,
        "language": args.language,
        "scancodes": "PS/2 set 1 scan codes, as returned by Qt nativeScanCode() and Win32 MapVirtualKey on Windows",
        "provenance": (
            f"Converted by tools/import_keyman_kmn.py from {args.source_url} "
            f"(keyboard version {version.group(1) if version else '?'}, sha256 {hashlib.sha256(raw).hexdigest()[:16]}). "
            f"License: {args.license}. Keys without a rule produce nothing; the numeric keypad and "
            f"CapsLock variants ({skipped} expanded rules) are not modelled."
        ),
        "keys": {
            f"0x{scan:02X}": {"label": SCAN_LABEL.get(scan, ""), **{l: keys[scan].get(l) for l in ("normal", "shift", "altgr", "shift_altgr")}}
            for scan in sorted(keys)
        },
        "rules": rules,
    }
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(keys)} keys, {len(rules)} context rules, {skipped} rules skipped (keypad/caps)", file=sys.stderr)


if __name__ == "__main__":
    main()
