"""Validation of the Hindi Remington GAIL layout (Keyman "Remington GAIL (SIL)" v1.1, converted).

Key tokens used below: a plain character is that US key cap, prefixed by S (Shift), A (AltGr) or SA (both):
    "d" = the D key, "S1" = Shift+1, "A,"= AltGr+comma, "SA/" = Shift+AltGr+slash.
Expected values come from the Keyman source and, for the letter keys, independently from the
IndiaTyping "Hindi Remington (GAIL)" chart, read by eye from the PDF (see CHART below).
"""
import unicodedata

import pytest

from cect.keymaps import load_keymap
from cect.keymaps.typist import plan_keystrokes, type_keys


@pytest.fixture(scope="module")
def gail():
    return load_keymap("remington_gail_hindi")


def key(km, token):
    mods = ""
    while len(token) > 1 and token[0] in "SA":
        mods, token = mods + token[0], token[1:]
    scan = {label: s for s, label in km.labels.items()}[token]
    return (scan, "S" in mods, "A" in mods)


def typed(km, *tokens):
    return type_keys(km, [key(km, t) for t in tokens])


def cps(text):
    return " ".join(f"U+{ord(c):04X}" for c in text)


# --- independent cross-check against the printed chart -----------------------------------------------
# (key cap, normal layer, Shift layer), transcribed from the IndiaTyping PDF. Shift+3 and Shift+4 differ
# between the chart and Keyman; they are pinned separately in test_known_differences_from_the_chart.
CHART = [
    ("q", "ु", "फ"), ("w", "ू", "ॅ"), ("e", "म", "म्"), ("r", "त", "त्"), ("t", "ज", "ज्"), ("y", "ल", "ल्"),
    ("u", "न", "न्"), ("i", "प", "प्"), ("o", "व", "व्"), ("p", "च", "च्"), ("[", "ख्", "क्ष्"), ("]", ",", "द्व"),
    ("a", "ं", "ा"), ("s", "े", "ै"), ("d", "क", "क्"), ("f", "ि", "थ्"), ("g", "ह", "ळ"), ("h", "ी", "भ्"),
    ("j", "र", "श्र"), ("k", "ा", "ज्ञ"), ("l", "स", "स्"), (";", "य", "रू"), ("'", "श्", "ष्"),
    ("z", "्र", "र्"), ("x", "ग", "ग्"), ("c", "ब", "ब्"), ("v", "अ", "ट"), ("b", "इ", "ठ"), ("n", "द", "छ"),
    ("m", "उ", "ड"), (",", "ए", "ढ"), (".", "ण्", "झ"), ("/", "ध्", "घ्"),
    ("1", "1", "।"), ("2", "2", "/"), ("5", "5", "-"), ("6", "6", "‘"), ("7", "7", "’"), ("8", "8", "द्ध"),
    ("9", "9", "त्र"), ("0", "0", "ऋ"), ("-", ";", "."), ("`", "़", "द्य"),
]


@pytest.mark.parametrize("cap, normal, shifted", CHART)
def test_normal_and_shift_layers_match_the_printed_chart(gail, cap, normal, shifted):
    assert typed(gail, cap) == normal
    assert typed(gail, "S" + cap) == shifted


def test_known_differences_from_the_chart(gail):
    # The chart prints ':' on Shift+3 and the obelus on Shift+4. Keyman types visarga (colon only after a
    # digit or punctuation) and '*'. We ship Keyman unchanged; these tests pin that choice.
    assert typed(gail, "S3") == "ः"
    assert typed(gail, "S4") == "*"
    assert typed(gail, "SA7") == "÷"


# --- number row and digits ---------------------------------------------------------------------------

def test_digits_are_latin_by_default_and_devanagari_on_altgr(gail):
    assert "".join(typed(gail, d) for d in "0123456789") == "0123456789"
    assert "".join(typed(gail, "A" + d) for d in "0123456789") == "०१२३४५६७८९"


def test_number_row_punctuation(gail):
    assert typed(gail, "S1") == "।"
    assert typed(gail, "S2") == "/"
    assert typed(gail, "S5") == "-"
    assert typed(gail, "S-") == "."
    assert typed(gail, "]") == ","
    assert typed(gail, "-") == ";"
    assert typed(gail, "\\") == "(" and typed(gail, "S\\") == ")"


def test_colon_after_a_digit_but_visarga_after_a_letter(gail):
    assert typed(gail, "1", "0", "S3", "3", "0") == "10:30"  # a time
    assert typed(gail, "d", "S3") == "कः"


def test_question_and_exclamation_marks_need_shift_altgr(gail):
    assert typed(gail, "SA/") == "?"
    assert typed(gail, "SA0") == "!"
    assert typed(gail, "A=") == "+" and typed(gail, "SA=") == "="


def test_double_danda(gail):
    assert typed(gail, "S1", "S1") == "॥"


# --- halant, half letters and conjuncts --------------------------------------------------------------

def test_half_letter_then_consonant_forms_a_conjunct(gail):
    assert typed(gail, "Sd", "e") == "क्म"  # क् + म
    assert cps(typed(gail, "Sd", "e")) == "U+0915 U+094D U+092E"


def test_half_letter_followed_by_the_a_matra_key_completes_the_letter(gail):
    # Keyman rule: consonant + halant, then the aa-matra key, gives the plain consonant.
    assert typed(gail, "Sd", "k") == "क"


def test_explicit_halant_key(gail):
    assert typed(gail, "d", "S=", "e") == "क्म"


def test_rakar_and_reph(gail):
    assert cps(typed(gail, "i", "z")) == "U+092A U+094D U+0930"  # प + ्र  = प्र
    assert cps(typed(gail, "Sz", "d")) == "U+0930 U+094D U+0915"  # र् + क  = र्क


@pytest.mark.parametrize(
    "tokens, expected",
    [
        (("S9",), "त्र"), (("Sj",), "श्र"), (("Sk",), "ज्ञ"), (("S8",), "द्ध"), (("S`",), "द्य"),
        (("SA[",), "क्ष"), (("S[", "k"), "क्ष"), (("S]",), "द्व"),
    ],
)
def test_conjunct_keys(gail, tokens, expected):
    assert typed(gail, *tokens) == unicodedata.normalize("NFC", expected)


# --- matra ordering (logical Unicode order, not legacy typewriter order) -----------------------------

def test_i_matra_is_typed_after_the_consonant(gail):
    assert cps(typed(gail, "d", "f")) == "U+0915 U+093F"  # कि


def test_legacy_typewriter_order_is_not_reordered(gail):
    # Legacy Remington types the matra first; this Unicode layout does not reorder it.
    assert cps(typed(gail, "f", "d")) == "U+093F U+0915"


@pytest.mark.parametrize(
    "tokens, expected",
    [
        (("d", "k"), "का"), (("d", "h"), "की"), (("d", "q"), "कु"), (("d", "w"), "कू"), (("d", "="), "कृ"),
        (("d", "s"), "के"), (("d", "Ss"), "कै"), (("d", "a"), "कं"),
    ],
)
def test_matras_follow_the_consonant(gail, tokens, expected):
    assert typed(gail, *tokens) == expected


# --- vowels built from parts, nukta, ZWJ/ZWNJ ---------------------------------------------------------

@pytest.mark.parametrize(
    "tokens, expected",
    [
        (("v", "k"), "आ"), ((",", "s"), "ऐ"), (("v", "k", "s"), "ओ"), (("v", "k", "Ss"), "औ"),
        (("m", "q"), "ऊ"), (("v", "k", "Sw"), "ऑ"), ((",", "Sw"), "ऍ"),
        (("d", "`"), "क़"),  # क़ as the single code point U+0958, not क + nukta
        (("Sm", "`"), "ड़"),  # ड़ as U+095C
    ],
)
def test_composed_characters_are_real_unicode_code_points(gail, tokens, expected):
    assert typed(gail, *tokens) == expected


def test_zero_width_joiners(gail):
    assert typed(gail, "A`") == "‌"  # ZWNJ
    assert typed(gail, "SA`") == "‍"  # ZWJ


# --- modifier model ----------------------------------------------------------------------------------

def test_altgr_layer_examples(gail):
    assert typed(gail, "Ac") == "ड़"  # ड़
    assert typed(gail, "Ap") == "श" and typed(gail, "SAp") == "ढ़"  # ढ़ as U+095D
    assert typed(gail, "A,") == "ँ"
    assert typed(gail, "A1") == "१"


def test_keys_without_a_rule_type_nothing(gail):
    assert gail.press("", 0x39, shift=True) is None  # Shift+Space: the layout defines nothing
    assert gail.press("", 0x60) is None  # not a key on the main block


def test_space_bar_passes_through(gail):
    assert typed(gail, "d", " ", "d") == "क क"


# --- Unicode, not legacy-font, output ----------------------------------------------------------------

def _all_outputs(km):
    for layers in km.keys.values():
        yield from (t for t in layers.values() if t)
    yield from (r.output for r in km.rules)


def test_every_output_is_unicode_devanagari_or_plain_punctuation(gail):
    allowed_extra = set("‌‍‘’“”×÷")
    for out in _all_outputs(gail):
        for ch in out:
            assert 0x0900 <= ord(ch) <= 0x097F or 0x20 <= ord(ch) <= 0x7E or ch in allowed_extra, (out, hex(ord(ch)))


def test_no_latin_letters_are_ever_produced(gail):
    # Legacy (Kruti Dev-style) Remington fonts type Latin letters that merely look Devanagari.
    letters = [out for out in _all_outputs(gail) if any(c.isascii() and c.isalpha() for c in out)]
    assert letters == []


def test_rules_are_unambiguous(gail):
    seen = {}
    for rule in gail.rules:
        ident = (rule.context, rule.scan_code, rule.shift, rule.altgr)
        assert ident not in seen or seen[ident] == rule.output, ident
        seen[ident] = rule.output


def test_longest_matching_context_wins(gail):
    # Keyman's precedence: 'consonant + halant + ZWJ' beats 'consonant + halant' for the same key.
    assert typed(gail, "d", "S=", "SA`", "k") == "क"


# --- typing real text end to end ---------------------------------------------------------------------

SAMPLES = [
    "परीक्षा", "क्या आप तैयार हैं?", "हाँ, (पूरी) तैयारी है - धन्यवाद!",
    "भारत में 21/09/2026 को परीक्षा होगी। समय 10:30 बजे है।",
    "सफलता नियमित अभ्यास और कठिन परिश्रम से ही संभव है। परीक्षा कक्ष में बैठते समय अपने मन को शांत रखना अत्यंत आवश्यक है।",
    "कंप्यूटर दक्षता प्रमाणीकरण परीक्षा एक महत्वपूर्ण माध्यम है जिसके द्वारा विभिन्न सरकारी विभागों में डाटा एंट्री ऑपरेटर और सहायक ग्रेड तीन के पदों पर योग्य उम्मीदवारों का चयन किया जाता है।",
    "जहाँ प्रत्येक राज्य की अपनी विशिष्ट पहचान और भाषा है। ओम औषधि ऊर्जा ऐसा आज्ञा श्रीमान् क्षत्रिय ज्ञान द्वारा",
    "पेड़ ज़रूर फ़ोन ढ़ाई क़ानून ख़बर ग़लत",  # nukta letters: the layout emits precomposed U+0958-U+095F
]


@pytest.mark.parametrize("sample", SAMPLES)
def test_a_virtual_typist_can_produce_real_passages_exactly(gail, sample):
    plan = plan_keystrokes(gail, sample)
    assert plan is not None, "layout cannot type this text"
    # Compared in NFC, as scoring does: the layout emits precomposed nukta letters such as U+095C.
    assert unicodedata.normalize("NFC", type_keys(gail, plan)) == unicodedata.normalize("NFC", sample)


def test_the_planner_refuses_text_the_layout_cannot_type(gail):
    assert plan_keystrokes(gail, "hello") is None  # Latin letters are not on this layout
