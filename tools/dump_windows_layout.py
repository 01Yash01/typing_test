"""Dump a Windows keyboard layout into a cect keymap JSON file (Windows only).

The layout is loaded into this process with LoadKeyboardLayout and queried with ToUnicodeEx, so the
table comes straight from the layout DLL instead of being typed in by hand. The layout is unloaded
again afterwards, and GetKeyboardLayoutList is compared before and after to confirm the user's
installed input methods were not changed.

Examples:
    python tools/dump_windows_layout.py --klid 00000439 --preview
    python tools/dump_windows_layout.py --klid 00000439 --id inscript_hindi --name "Hindi InScript" \
        --language hindi --out cect/keymaps/inscript_hindi.json
"""
import argparse
import ctypes
import datetime
import json
import sys
from ctypes import wintypes
from pathlib import Path

# Main alphanumeric block, PS/2 set 1 scan codes: digits row, QWERTY, home row, bottom row, space.
SCANCODES = (
    list(range(0x02, 0x0E))
    + list(range(0x10, 0x1C))
    + list(range(0x1E, 0x2A))
    + [0x2B]
    + list(range(0x2C, 0x36))
    + [0x39]
)
LAYERS = (("normal", False, False), ("shift", True, False), ("altgr", False, True), ("shift_altgr", True, True))

KLF_NOTELLSHELL = 0x80
MAPVK_VSC_TO_VK = 1
TOUNICODE_KEEP_KEYBOARD_STATE = 0x4  # Windows 10 1607+: do not let dead keys alter global state
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
US_ENGLISH_KLID = "00000409"


def _bind_user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LoadKeyboardLayoutW.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
    user32.LoadKeyboardLayoutW.restype = wintypes.HKL
    user32.UnloadKeyboardLayout.argtypes = [wintypes.HKL]
    user32.UnloadKeyboardLayout.restype = wintypes.BOOL
    user32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(wintypes.HKL)]
    user32.GetKeyboardLayoutList.restype = ctypes.c_int
    user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HKL]
    user32.MapVirtualKeyExW.restype = wintypes.UINT
    user32.ToUnicodeEx.argtypes = [
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
        wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL,
    ]
    user32.ToUnicodeEx.restype = ctypes.c_int
    return user32


def _installed_layouts(user32):
    count = user32.GetKeyboardLayoutList(0, None)
    handles = (wintypes.HKL * count)()
    user32.GetKeyboardLayoutList(count, handles)
    return sorted(int(ctypes.cast(h, ctypes.c_void_p).value or 0) for h in handles)


def _key_state(shift, altgr):
    state = (ctypes.c_ubyte * 256)()
    if shift:
        state[VK_SHIFT] = 0x80
    if altgr:  # AltGr is reported by Windows as Ctrl+Alt
        state[VK_CONTROL] = 0x80
        state[VK_MENU] = 0x80
    return state


def _translate(user32, hkl, scan, shift, altgr):
    """Return the text a key produces in one layer, or None (no output, dead key or control code)."""
    vk = user32.MapVirtualKeyExW(scan, MAPVK_VSC_TO_VK, hkl)
    if vk == 0:
        return None
    buf = ctypes.create_unicode_buffer(8)
    n = user32.ToUnicodeEx(vk, scan, _key_state(shift, altgr), buf, len(buf), TOUNICODE_KEEP_KEYBOARD_STATE, hkl)
    if n <= 0:  # 0 = no translation, <0 = dead key
        return None
    text = buf.value[:n]
    return None if any(ord(c) < 0x20 for c in text) else text


def dump_layout(klid):
    """Return {scancode: {layer: text|None}} for the layout with this KLID, plus US-English labels."""
    user32 = _bind_user32()
    before = _installed_layouts(user32)
    target = user32.LoadKeyboardLayoutW(klid, KLF_NOTELLSHELL)
    if not target:
        raise OSError(f"Windows could not load keyboard layout {klid} (error {ctypes.get_last_error()})")
    us = user32.LoadKeyboardLayoutW(US_ENGLISH_KLID, KLF_NOTELLSHELL)
    try:
        keys = {}
        for scan in SCANCODES:
            entry = {"label": _translate(user32, us, scan, False, False) or "" if scan != 0x39 else "Space"}
            for name, shift, altgr in LAYERS:
                entry[name] = _translate(user32, target, scan, shift, altgr)
            keys[scan] = entry
    finally:
        # Unload only what this run added, then confirm the user's list is exactly as we found it.
        for hkl in (target, us):
            if int(ctypes.cast(hkl, ctypes.c_void_p).value or 0) not in before:
                user32.UnloadKeyboardLayout(hkl)
    after = _installed_layouts(user32)
    if before != after:
        print(f"WARNING: keyboard layout list changed ({len(before)} -> {len(after)} layouts)", file=sys.stderr)
    return keys


def print_preview(keys):
    print(f"{'scan':<5} {'key':<6} {'normal':<8} {'shift':<8} {'altgr':<8} {'shift+altgr':<8}")
    for scan, entry in keys.items():
        cells = [(entry[name] or "-") for name, _, _ in LAYERS]
        print(f"0x{scan:02X}  {entry['label']:<6} " + " ".join(f"{c:<8}" for c in cells))


def write_json(keys, path, layout_id, name, language, klid):
    doc = {
        "id": layout_id,
        "name": name,
        "language": language,
        "scancodes": "PS/2 set 1 scan codes, as returned by Qt nativeScanCode() and Win32 MapVirtualKey on Windows",
        "provenance": (
            f"Generated by tools/dump_windows_layout.py from Windows keyboard layout {klid} "
            f"on {datetime.date.today().isoformat()}."
        ),
        "keys": {f"0x{scan:02X}": entry for scan, entry in keys.items()},
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    if sys.platform != "win32":
        sys.exit("This tool only runs on Windows.")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--klid", required=True, help="Windows keyboard layout id, e.g. 00000439")
    parser.add_argument("--preview", action="store_true", help="print the table instead of writing JSON")
    parser.add_argument("--id")
    parser.add_argument("--name")
    parser.add_argument("--language")
    parser.add_argument("--out")
    args = parser.parse_args()

    keys = dump_layout(args.klid)
    if args.preview:
        sys.stdout.reconfigure(encoding="utf-8")
        print_preview(keys)
        return
    if not (args.id and args.name and args.language and args.out):
        parser.error("--id, --name, --language and --out are required unless --preview is given")
    write_json(keys, args.out, args.id, args.name, args.language, args.klid)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
