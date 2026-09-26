import json

import pytest

from cect.profile import ExamProfile, ProfileError, builtin_profiles, load_profile

GOOD = {
    "name": "Test profile",
    "language": "hindi",
    "duration_seconds": 300,
    "timer_start": "start_button",
    "backspace_allowed": False,
    "scoring": "word",
    "min_net_wpm": 25,
    "min_accuracy": 90.5,
}


def test_builtin_profiles_load_and_match_the_prd():
    profiles = builtin_profiles()
    hindi, english = profiles["cpct-hindi"], profiles["cpct-english"]
    assert (hindi.language, hindi.duration_seconds, hindi.min_net_wpm, hindi.min_accuracy) == ("hindi", 900, 20, 85)
    assert (english.language, english.min_net_wpm) == ("english", 30)


def test_round_trip():
    assert ExamProfile.from_dict(GOOD).to_dict() == {**GOOD, "notes": ""}


@pytest.mark.parametrize(
    "patch, fragment",
    [
        ({"language": "french"}, "language"),
        ({"timer_start": "now"}, "timer_start"),
        ({"scoring": "words"}, "scoring"),
        ({"duration_seconds": 0}, "duration_seconds"),
        ({"duration_seconds": 12.5}, "duration_seconds"),
        ({"duration_seconds": True}, "duration_seconds"),
        ({"backspace_allowed": "yes"}, "backspace_allowed"),
        ({"min_net_wpm": -1}, "min_net_wpm"),
        ({"min_accuracy": 101}, "min_accuracy"),
        ({"name": "  "}, "name"),
    ],
)
def test_rejects_bad_values(patch, fragment):
    with pytest.raises(ProfileError, match=fragment):
        ExamProfile.from_dict({**GOOD, **patch})


def test_rejects_unknown_and_missing_fields():
    with pytest.raises(ProfileError, match="unknown.*duraton_seconds"):
        ExamProfile.from_dict({**GOOD, "duraton_seconds": 1})  # a typo must not be silently ignored
    with pytest.raises(ProfileError, match="missing.*scoring"):
        ExamProfile.from_dict({k: v for k, v in GOOD.items() if k != "scoring"})


def test_load_profile_errors_name_the_file(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProfileError, match="bad.json.*not valid JSON"):
        load_profile(bad_json)

    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ProfileError, match="expected a JSON object"):
        load_profile(not_object)

    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({**GOOD, "min_accuracy": 500}), encoding="utf-8")
    with pytest.raises(ProfileError, match="invalid.json.*min_accuracy"):
        load_profile(invalid)
