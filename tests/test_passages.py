import random
import re
import unicodedata

import pytest

from cect.keymaps import available_layouts, load_keymap
from cect.keymaps.typist import plan_keystrokes
from cect.passages import PassageError, build_source, load_passages

HINDI = load_passages("hindi")
ENGLISH = load_passages("english")


@pytest.mark.parametrize("passages", [HINDI, ENGLISH], ids=["hindi", "english"])
def test_passage_files_are_well_formed(passages):
    assert len({p.id for p in passages}) == len(passages)
    for p in passages:
        assert p.text == p.text.strip() and "  " not in p.text, p.id
        assert p.text == unicodedata.normalize("NFC", p.text), p.id
        assert p.word_count >= 40, p.id


def test_english_passages_use_only_keys_on_a_standard_keyboard():
    for p in ENGLISH:
        assert all(0x20 <= ord(c) <= 0x7E for c in p.text), p.id


def test_hindi_passages_are_typable_on_every_shipped_hindi_layout():
    layouts = [km for km in map(load_keymap, available_layouts()) if km.language == "hindi"]
    assert {km.id for km in layouts} >= {"remington_gail_hindi", "inscript_hindi"}
    for km in layouts:
        for p in HINDI:
            if km.rules:  # context rules: only a virtual typist can prove typability
                assert plan_keystrokes(km, p.text) is not None, (km.id, p.id)
            else:
                assert km.missing_chars(p.text) == frozenset(), (km.id, p.id)


@pytest.mark.parametrize("passages", [HINDI, ENGLISH], ids=["hindi", "english"])
def test_passages_mix_prose_with_numbers_dates_and_punctuation(passages):
    joined = " ".join(p.text for p in passages)
    assert re.search(r"\d{4}", joined)  # a year
    assert re.search(r"\d+:\d+", joined)  # a time
    assert all(mark in joined for mark in ",()-")


def test_a_chosen_passage_is_used_as_is():
    assert build_source(HINDI, "library-notice", 15, 40) == next(p for p in HINDI if p.id == "library-notice").text


def test_random_source_is_long_enough_for_the_time_and_reproducible():
    a = build_source(ENGLISH, None, 5, 40, random.Random(1))
    assert len(a.split()) >= 5 * 40
    assert a == build_source(ENGLISH, None, 5, 40, random.Random(1))


def test_short_tests_do_not_get_needlessly_long_sources():
    assert len(build_source(ENGLISH, None, 1, 20, random.Random(3)).split()) < 200


def test_unknown_language_is_reported():
    with pytest.raises(PassageError):
        load_passages("french")
