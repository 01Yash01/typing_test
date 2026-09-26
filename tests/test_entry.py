import pytest

from cect.entry import EntryPolicy, KeyInput
from cect.keymaps import load_keymap

GAIL = load_keymap("remington_gail_hindi")
LABEL_TO_SCAN = {label: scan for scan, label in GAIL.labels.items()}


def hindi(backspace=True, newline=False):
    return EntryPolicy(GAIL, backspace_allowed=backspace, allow_newline=newline)


def english(backspace=True):
    return EntryPolicy(None, backspace_allowed=backspace)


def press(label, shift=False, altgr=False, **extra):
    return KeyInput(scan_code=LABEL_TO_SCAN[label], shift=shift, altgr=altgr, **extra)


def test_hindi_keys_go_through_the_layout():
    assert hindi().handle("", press("d")) == (0, "क")
    assert hindi().handle("", press("d", shift=True)) == (0, "क्")


def test_hindi_context_rules_edit_the_text_before_the_caret():
    assert hindi().handle("अ", press("k")) == (1, "आ")  # अ + ा becomes आ
    assert hindi().handle("क्", press("k")) == (2, "क")  # the context is क + halant, so both are replaced


def test_hindi_ignores_keys_the_layout_does_not_define():
    assert hindi().handle("", KeyInput(scan_code=0x53)) is None  # Delete
    assert hindi().handle("", KeyInput(scan_code=0x2A)) is None  # a bare Shift press


def test_physical_key_decides_not_the_text_the_os_would_type():
    # Whatever Windows layout is active, the D key types क.
    assert hindi().handle("", press("d", text="d")) == (0, "क")
    assert hindi().handle("", press("d", text="क")) == (0, "क")


def test_backspace_removes_one_character_when_allowed():
    assert hindi().handle("कि", KeyInput(action="backspace")) == (1, "")


def test_backspace_on_empty_text_does_nothing():
    assert hindi().handle("", KeyInput(action="backspace")) is None


def test_locked_backspace_does_nothing():
    assert hindi(backspace=False).handle("कि", KeyInput(action="backspace")) is None
    assert english(backspace=False).handle("ab", KeyInput(action="backspace")) is None


@pytest.mark.parametrize("newline, expected", [(True, (0, "\n")), (False, None)])
def test_enter_only_types_a_newline_when_the_source_has_them(newline, expected):
    assert hindi(newline=newline).handle("क", KeyInput(action="enter")) == expected


def test_shortcuts_are_ignored():
    assert hindi().handle("", press("d", shortcut=True)) is None  # Ctrl+D / Alt+D
    assert english().handle("", KeyInput(text="\x03", shortcut=True)) is None  # Ctrl+C
    assert hindi().handle("क", KeyInput(action="backspace", shortcut=True)) is None  # Ctrl+Backspace


def test_altgr_selects_the_altgr_layer_not_a_shortcut():
    assert hindi().handle("", press("1", altgr=True)) == (0, "१")


def test_keypad_digits_and_operators_type_as_themselves():
    assert hindi().handle("", KeyInput(scan_code=0x4F, keypad=True, text="1")) == (0, "1")
    assert hindi().handle("", KeyInput(scan_code=0x35, keypad=True, text="/")) == (0, "/")
    assert hindi().handle("", KeyInput(scan_code=0x4F, keypad=True, text="")) is None  # NumLock off


def test_english_types_what_the_system_keyboard_produces():
    assert english().handle("", KeyInput(text="a")) == (0, "a")
    assert english().handle("", KeyInput(text="A", shift=True)) == (0, "A")
    assert english().handle("", KeyInput(text=" ")) == (0, " ")


@pytest.mark.parametrize("text", ["", "\t", "\x1b", "\x7f", "\r"])
def test_english_ignores_control_characters(text):
    assert english().handle("", KeyInput(text=text)) is None


def test_unknown_actions_are_ignored():
    assert english().handle("ab", KeyInput(action="delete")) is None
