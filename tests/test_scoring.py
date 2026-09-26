import random
from dataclasses import replace

import pytest

from cect.profile import ExamProfile
from cect.scoring import WordDiff, _align, lcs_info, normalize, score, split_words, word_diff

KEYSTROKE = ExamProfile(
    name="test", language="hindi", duration_seconds=900, timer_start="first_keystroke",
    backspace_allowed=True, scoring="keystroke", min_net_wpm=20, min_accuracy=85,
)
WORD = replace(KEYSTROKE, scoring="word")

SRC = "the quick brown fox jumps over the lazy dog "
L = len(SRC)

PASSAGE = (
    "सफलता नियमित अभ्यास और कठिन परिश्रम से ही संभव है। परीक्षा कक्ष में बैठते समय अपने मन को शांत "
    "रखना अत्यंत आवश्यक है। "
)


def run(typed, profile=KEYSTROKE, elapsed=60, **kwargs):
    return score(SRC, typed, elapsed, profile, **kwargs)


# --- lcs_info ---------------------------------------------------------------------------------------

def _lcs_len(a, b):
    row = [0] * (len(b) + 1)
    for ca in a:
        prev, row[0] = row[0], 0
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], prev + 1 if ca == cb else max(row[j], row[j - 1])
    return row[-1]


def _min_prefix(a, b):
    target = _lcs_len(a, b)
    return next(j for j in range(len(a) + 1) if _lcs_len(a[:j], b) == target)


def test_lcs_info_matches_dynamic_programming_reference():
    rng = random.Random(1234)
    for _ in range(600):
        a = "".join(rng.choice("abc ") for _ in range(rng.randint(0, 14)))
        b = "".join(rng.choice("abc ") for _ in range(rng.randint(0, 14)))
        assert lcs_info(a, b) == (_lcs_len(a, b), _min_prefix(a, b)), (a, b)


def test_lcs_info_handles_exam_sized_text():
    text = PASSAGE * 25  # ~3,000 characters
    assert lcs_info(text, text[:1500] + text[1501:]) == (len(text) - 1, len(text))


# --- word alignment ---------------------------------------------------------------------------------

def _best_prefix_edit_distance(src, typed):
    """Independent reference: Levenshtein distance from `typed` to the best-matching source prefix."""
    n, m = len(src), len(typed)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (src[i - 1] != typed[j - 1]))
    return min(d[i][m] for i in range(n + 1))


def test_alignment_is_well_formed_and_minimal_cost():
    rng = random.Random(99)
    for _ in range(800):
        src = [rng.choice("abc") for _ in range(rng.randint(0, 9))]
        typed = [rng.choice("abc") for _ in range(rng.randint(0, 9))]
        ops = _align(src, typed)
        i = j = cost = 0
        for tag, i1, i2, j1, j2 in ops:
            assert (i1, j1) == (i, j), (src, typed, ops)  # contiguous
            if tag == "equal":
                assert src[i1:i2] == typed[j1:j2]
            else:
                cost += max(i2 - i1, j2 - j1)
            i, j = i2, j2
        assert j == len(typed) and i <= len(src)  # every typed word is accounted for
        assert cost == _best_prefix_edit_distance(src, typed), (src, typed, ops)


# --- normalisation ----------------------------------------------------------------------------------

def test_line_endings_are_unified():
    assert normalize("a\r\nb\rc") == "a\nb\nc"


def test_equivalent_devanagari_spellings_compare_equal():
    precomposed, decomposed = "क़", "क़"  # क़ as one code point vs क + nukta
    assert normalize(precomposed) == normalize(decomposed)
    src = "क़ता है "
    assert score(src, "क़ता है ", 60, KEYSTROKE).accuracy == 100.0


def test_split_words_keeps_trailing_whitespace_and_drops_leading():
    assert split_words("  ab  cd\nef") == ["ab  ", "cd\n", "ef"]


# --- keystroke mode ---------------------------------------------------------------------------------

def test_perfect_typing():
    r = run(SRC)
    assert (r.correct_keystrokes, r.mistakes, r.accuracy) == (L, 0, 100.0)
    assert r.gross_wpm == r.net_wpm == round(L / 5, 2)


def test_one_skipped_character_costs_one_keystroke():
    r = run(SRC.replace("the quick", "te quick", 1))
    assert r.mistakes == 1
    assert r.correct_keystrokes == L - 1
    assert r.accuracy == round((L - 1) / L * 100, 2)


def test_one_extra_character_costs_one_keystroke():
    r = run(SRC.replace("the quick", "thee quick", 1))
    assert (r.correct_keystrokes, r.mistakes) == (L, 1)
    assert r.accuracy == round(L / (L + 1) * 100, 2)


def test_prototype_positional_comparison_bug_is_gone():
    # The prototype scored this ~5%: every character after the slip was compared one slot out.
    typed = PASSAGE[:2] + PASSAGE[3:]
    r = score(PASSAGE, typed, 60, KEYSTROKE)
    assert r.mistakes == 1
    assert r.accuracy > 99


def test_final_wrong_word_is_not_paired_with_an_identical_word_further_ahead():
    # 'we' is wrong at position 5 but appears again at position 7; skipping "food and" to reach it
    # would be two mistakes, and treating it as a slip is one substitution.
    src = "we like to eat food and we like to drink tea today "
    r = score(src, "we like to eat we", 60, KEYSTROKE)
    assert r.correct_keystrokes == len("we like to eat ")
    assert r.mistakes == len("we")


def test_repetitive_drill_text_aligns_correctly():
    src = "abcd " * 40
    words = ["abcd "] * 40
    words[5] = words[20] = words[30] = "zzzz "
    r = score(src, "".join(words), 60, KEYSTROKE)
    assert r.mistakes == 3 * 4
    assert r.correct_keystrokes == 37 * 5 + 3


def test_skipped_word_counts_against_accuracy():
    r = run(SRC.replace("brown ", ""))
    assert r.mistakes == len("brown ")
    assert r.correct_keystrokes == L - len("brown ")


def test_stopping_early_is_not_penalised():
    r = run("the quick brown ")
    assert (r.correct_keystrokes, r.mistakes, r.accuracy) == (16, 0, 100.0)


def test_partial_final_word_is_not_penalised():
    r = run("the quic")
    assert (r.correct_keystrokes, r.mistakes, r.accuracy) == (8, 0, 100.0)


def test_typing_past_the_end_of_the_source_is_penalised():
    r = run(SRC + "extra words ")
    assert r.correct_keystrokes == L
    assert r.mistakes == len("extra words ")


def test_wrong_letters_keep_partial_credit():
    r = run(SRC.replace("quick", "qzzzk"))  # q, k and the space still match in order
    assert r.mistakes == 3
    assert r.correct_keystrokes == L - 3


def test_extra_space_is_one_mistake():
    r = run(SRC.replace("the quick", "the  quick", 1))
    assert (r.correct_keystrokes, r.mistakes) == (L, 1)


# --- word mode --------------------------------------------------------------------------------------

def test_word_mode_gives_no_credit_for_a_wrong_word():
    r = run(SRC.replace("quick", "qzzzk"), WORD)
    assert r.mistake_unit == "words"
    assert r.mistakes == 1
    assert r.correct_keystrokes == L - len("quick ")
    assert r.accuracy == round(8 / 9 * 100, 2)


def test_word_mode_ignores_extra_spacing():
    r = run(SRC.replace("the quick", "the  quick", 1), WORD)
    assert (r.correct_keystrokes, r.mistakes, r.accuracy) == (L, 0, 100.0)


def test_word_mode_counts_a_partial_final_word_as_wrong():
    r = run("the quic", WORD)
    assert (r.mistakes, r.accuracy) == (1, 50.0)


def test_word_mode_omitted_and_extra_words():
    assert run(SRC.replace("brown ", ""), WORD).mistakes == 1
    assert run(SRC.replace("brown ", "brown very "), WORD).mistakes == 1


# --- speed arithmetic and pass mark -----------------------------------------------------------------

def test_speed_arithmetic():
    src = "abcd " * 60  # 300 keystrokes
    assert score(src, src, 60, KEYSTROKE).net_wpm == 60.0
    assert score(src, src, 120, KEYSTROKE).net_wpm == 30.0
    r = score(src, src, 60, KEYSTROKE, key_presses=450)
    assert (r.total_keystrokes, r.gross_wpm, r.net_wpm) == (450, 90.0, 60.0)


def test_pass_mark_speed_boundary():
    src = "abcd " * 100
    assert score(src, src, 300, KEYSTROKE).passed  # exactly 20.00 net WPM
    slower = score(src, src, 301, KEYSTROKE)
    assert slower.net_wpm == 19.93
    assert not slower.passed


def test_pass_mark_accuracy_boundary():
    src = "abcd " * 20
    speed_ignored = replace(KEYSTROKE, min_net_wpm=0)

    def with_wrong_words(count):
        words = ["abcd "] * 20
        for i in (2, 6, 10, 14)[:count]:
            words[i] = "zzzz "
        return score(src, "".join(words), 60, speed_ignored)

    assert (with_wrong_words(3).accuracy, with_wrong_words(3).passed) == (88.0, True)
    assert (with_wrong_words(4).accuracy, with_wrong_words(4).passed) == (84.0, False)


# --- degenerate input -------------------------------------------------------------------------------

@pytest.mark.parametrize("typed", ["", "   ", "\n"])
def test_nothing_typed(typed):
    r = run(typed)
    assert (r.total_keystrokes if typed == "" else r.correct_keystrokes) == 0
    assert (r.accuracy, r.net_wpm, r.passed) == (0.0, 0.0, False)


def test_empty_source_is_rejected():
    with pytest.raises(ValueError):
        score("  ", "abc", 60, KEYSTROKE)


def test_zero_elapsed_time_gives_zero_speed_not_a_crash():
    r = run(SRC, elapsed=0)
    assert (r.gross_wpm, r.net_wpm) == (0.0, 0.0)


# --- word_diff (mistake review) ----------------------------------------------------------------------

def test_perfect_typing_is_all_correct():
    diffs = word_diff(SRC, SRC)
    assert [d.status for d in diffs] == ["correct"] * len(SRC.split())
    assert all(d.source == d.typed for d in diffs)


def test_a_wrong_word_is_reported_with_both_spellings():
    diffs = word_diff(SRC, SRC.replace("quick", "qzzzk"))
    wrong = [d for d in diffs if d.status != "correct"]
    assert wrong == [WordDiff("wrong", "quick", "qzzzk")]


def test_a_skipped_word_is_reported_as_missing():
    diffs = word_diff(SRC, SRC.replace("brown ", ""))
    missing = [d for d in diffs if d.status == "missing"]
    assert len(missing) == 1 and missing[0].source == "brown" and missing[0].typed == ""


def test_an_inserted_word_is_reported_as_extra():
    diffs = word_diff(SRC, SRC.replace("brown", "brown very"))
    extra = [d for d in diffs if d.status == "extra"]
    assert len(extra) == 1 and extra[0].typed == "very" and extra[0].source == ""


def test_stopping_early_leaves_the_untyped_tail_out_of_the_review():
    diffs = word_diff(SRC, "the quick brown ")
    assert [d.status for d in diffs] == ["correct"] * 3


def test_a_partial_final_word_is_reviewed_but_not_the_rest_of_the_source():
    diffs = word_diff(SRC, "the quic")
    assert [d.status for d in diffs] == ["correct", "wrong"]
    assert diffs[-1] == WordDiff("wrong", "quick", "quic")


def test_typing_past_the_end_of_the_source_is_all_extra():
    diffs = word_diff(SRC, SRC + "extra words ")
    tail = diffs[len(SRC.split()):]
    assert [d.status for d in tail] == ["extra", "extra"]


@pytest.mark.parametrize(
    "typed",
    ["the quick brown fox jumps over the lazy dog", "te quick brown fox", "the quick brown ", "the quic",
     "the quick brown fox jumps over the lazy dog extra words", SRC.replace("brown", "brown very")],
)
def test_mistake_count_matches_the_scorer_in_word_mode(typed):
    diffs = word_diff(SRC, typed)
    assert sum(1 for d in diffs if d.status != "correct") == run(typed, WORD).mistakes


def test_word_diff_rejects_an_empty_source():
    with pytest.raises(ValueError):
        word_diff("  ", "abc")
