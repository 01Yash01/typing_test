from dataclasses import replace

import pytest

from cect.history import HistoryEntry, append_history, load_history
from cect.profile import builtin_profiles
from cect.scoring import score

PROFILE = builtin_profiles()["cpct-hindi"]
RESULT = score("the cat sat ", "the cat sat ", 30, replace(PROFILE, language="english"))


def entry(**overrides):
    base = dict(id="fixed-id", timestamp=1000.0, profile_name=PROFILE.name, language="hindi",
                layout_name="Hindi Remington GAIL", duration_seconds=900, net_wpm=20.0, gross_wpm=22.0,
                accuracy=95.0, passed=True)
    return HistoryEntry(**{**base, **overrides})


def test_from_result_fills_in_every_field_from_the_score_and_profile():
    e = HistoryEntry.from_result(RESULT, PROFILE, "Hindi InScript", clock=lambda: 42.0)
    assert e.timestamp == 42.0
    assert (e.profile_name, e.language, e.layout_name, e.duration_seconds) == (
        PROFILE.name, PROFILE.language, "Hindi InScript", PROFILE.duration_seconds)
    assert (e.net_wpm, e.gross_wpm, e.accuracy, e.passed) == (RESULT.net_wpm, RESULT.gross_wpm, RESULT.accuracy, RESULT.passed)
    assert len(e.id) == 32  # a uuid4 hex


def test_from_result_gives_each_attempt_a_distinct_id():
    a = HistoryEntry.from_result(RESULT, PROFILE, "x")
    b = HistoryEntry.from_result(RESULT, PROFILE, "x")
    assert a.id != b.id


def test_round_trip(tmp_path):
    path = tmp_path / "history.json"
    append_history(entry(id="a"), path)
    append_history(entry(id="b", net_wpm=25.0), path)
    loaded = load_history(path)
    assert [e.id for e in loaded] == ["a", "b"]  # oldest first
    assert loaded[1].net_wpm == 25.0


def test_missing_history_file_is_an_empty_list(tmp_path):
    assert load_history(tmp_path / "absent.json") == []


@pytest.mark.parametrize("content", ["{not json", "{}", '{"a": 1}'])
def test_damaged_or_non_list_history_is_treated_as_empty(tmp_path, content):
    path = tmp_path / "history.json"
    path.write_text(content, encoding="utf-8")
    assert load_history(path) == []


def test_one_malformed_row_does_not_lose_the_rest(tmp_path):
    path = tmp_path / "history.json"
    path.write_text('[{"id": "ok", "timestamp": 1, "profile_name": "p", "language": "hindi", '
                     '"layout_name": "l", "duration_seconds": 60, "net_wpm": 1, "gross_wpm": 1, '
                     '"accuracy": 1, "passed": true}, {"garbage": true}]', encoding="utf-8")
    loaded = load_history(path)
    assert [e.id for e in loaded] == ["ok"]


def test_history_is_capped_at_the_given_limit(tmp_path):
    path = tmp_path / "history.json"
    for i in range(5):
        append_history(entry(id=str(i)), path, limit=3)
    assert [e.id for e in load_history(path)] == ["2", "3", "4"]  # the three most recent


def test_failing_to_save_history_is_silent(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    append_history(entry(), blocker / "history.json")  # parent "directory" is a file: must not raise
