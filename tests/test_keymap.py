import pytest

from cect.keymaps import KeyMap, KeymapError, available_layouts, load_keymap

# The two Hindi passages from the PRD prototype (instruct.md).
PASSAGES = [
    "सफलता नियमित अभ्यास और कठिन परिश्रम से ही संभव है। परीक्षा कक्ष में बैठते समय अपने मन को शांत रखना अत्यंत आवश्यक है। "
    "जब आप कीबोर्ड पर अपनी उंगलियों को सही स्थिति में रखते हैं, तो आपकी गति और सटीकता दोनों में निरंतर सुधार होता है। "
    "भारत एक विशाल और विविध संस्कृतियों वाला देश है जहाँ प्रत्येक राज्य की अपनी विशिष्ट पहचान और भाषा है।",
    "कंप्यूटर दक्षता प्रमाणीकरण परीक्षा एक महत्वपूर्ण माध्यम है जिसके द्वारा विभिन्न सरकारी विभागों में डाटा एंट्री ऑपरेटर और "
    "सहायक ग्रेड तीन के पदों पर योग्य उम्मीदवारों का चयन किया जाता है। परीक्षा के दौरान बैकस्पेस कुंजी का उपयोग सीमित या "
    "वर्जित हो सकता है, इसलिए शुद्धता पर ध्यान देना आवश्यक है।",
]


@pytest.fixture(scope="module")
def inscript():
    return load_keymap("inscript_hindi")


def test_inscript_is_listed_and_documents_its_origin(inscript):
    assert "inscript_hindi" in available_layouts()
    assert "00010439" in inscript.provenance


@pytest.mark.parametrize(
    "scan, shift, altgr, expected",
    [
        (0x25, False, False, "क"),  # K
        (0x25, True, False, "ख"),
        (0x24, False, False, "र"),  # J
        (0x20, False, False, "्"),  # D: halant
        (0x21, False, False, "ि"),  # F
        (0x22, False, False, "ु"),  # G
        (0x1E, False, False, "ो"),  # A
        (0x1F, False, False, "े"),  # S
        (0x12, False, False, "ा"),  # E
        (0x13, False, False, "ी"),  # R
        (0x15, False, False, "ब"),  # Y
        (0x15, True, False, "भ"),
        (0x2D, False, False, "ं"),  # X
        (0x2D, True, False, "ँ"),
        (0x34, True, False, "।"),  # Shift + period
        (0x02, False, True, "१"),  # AltGr + 1: Devanagari digit
        (0x35, True, True, "?"),  # Shift + AltGr + slash
        (0x39, False, False, " "),
    ],
)
def test_known_inscript_positions(inscript, scan, shift, altgr, expected):
    assert inscript.translate(scan, shift, altgr) == expected


def test_keys_that_produce_nothing_return_none(inscript):
    assert inscript.translate(0x2C) is None  # Z has no normal-layer output in this layout
    assert inscript.translate(0x60) is None  # not in the table at all


def test_prototype_passages_are_fully_typable(inscript):
    for passage in PASSAGES:
        assert inscript.missing_chars(passage) == frozenset()


def test_key_for_finds_a_key_that_types_each_character(inscript):
    for char in set("".join(PASSAGES)):
        key = inscript.key_for(char)
        assert key is not None, f"no key for {char!r} (U+{ord(char):04X})"
        assert inscript.translate(*key) == char


def test_missing_chars_reports_untypable_characters_and_ignores_newlines():
    tiny = KeyMap.from_dict({"id": "t", "name": "t", "language": "hindi", "keys": {"0x1E": {"normal": "a"}}})
    assert tiny.missing_chars("abc\n") == {"b", "c"}


def test_unknown_layout_is_reported_with_the_available_names():
    with pytest.raises(KeymapError, match="no keymap named 'nope'.*inscript_hindi"):
        load_keymap("nope")


GOOD_KEYS = {"0x1E": {"normal": "a"}}


@pytest.mark.parametrize(
    "doc, fragment",
    [
        ({"id": "x", "name": "x", "language": "hindi"}, "missing field 'keys'"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"zz": {"normal": "a"}}}, "not hexadecimal"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"0x00": {"normal": "a"}}}, "outside"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"0x1E": {}, "0x1e": {}}}, "appears twice"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"0x1E": {"normal": "a", "bogus": "b"}}}, "unknown field"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"0x1E": {"normal": ""}}}, "text or null"),
        ({"id": "x", "name": "x", "language": "hindi", "keys": {"0x1E": {"shift": 5}}}, "text or null"),
    ],
)
def test_rejects_malformed_keymaps(doc, fragment):
    with pytest.raises(KeymapError, match=fragment):
        KeyMap.from_dict(doc)


# --- context rules ----------------------------------------------------------------------------------

def _with_rules(rules):
    return KeyMap.from_dict({"id": "t", "name": "t", "language": "hindi", "keys": {"0x1E": {"normal": "a"}}, "rules": rules})


def _rule(context, output, key="0x1E", shift=False, altgr=False):
    return {"context": context, "key": key, "shift": shift, "altgr": altgr, "output": output}


def test_press_prefers_the_longest_matching_context():
    km = _with_rules([_rule("b", "X"), _rule("ab", "Y")])
    assert km.press("zab", 0x1E) == (2, "Y")
    assert km.press("zzb", 0x1E) == (1, "X")
    assert km.press("zzz", 0x1E) == (0, "a")  # no rule: the key's plain output


def test_equal_length_contexts_keep_file_order():
    km = _with_rules([_rule("b", "first"), _rule("b", "second")])
    assert km.press("b", 0x1E) == (1, "first")


def test_rules_only_apply_to_their_own_modifier_state():
    km = _with_rules([_rule("b", "X", shift=True)])
    assert km.press("b", 0x1E) == (0, "a")
    assert km.press("b", 0x1E, shift=True) == (1, "X")


def test_rule_outputs_count_as_typable_characters():
    km = _with_rules([_rule("a", "आ")])
    assert "आ" in km.typable_chars


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ({"context": "b", "key": "0x1E", "shift": False, "altgr": False}, "exactly"),
        ({**_rule("b", "X"), "extra": 1}, "exactly"),
        (_rule("", "X"), "non-empty"),
        (_rule("b", "X", key="zz"), "hexadecimal"),
        (_rule("b", "X", key="0x00"), "outside"),
        ({**_rule("b", "X"), "shift": "yes"}, "true or false"),
    ],
)
def test_malformed_rules_are_rejected(bad, fragment):
    with pytest.raises(KeymapError, match=fragment):
        _with_rules([bad])
