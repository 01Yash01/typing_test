import random

from cect.profile import builtin_profiles
from cect.settings import load_settings, save_settings
from cect.setup import SYSTEM_KEYBOARD, SetupChoice, build_session, effective_profile, layouts_for

PROFILES = builtin_profiles()


def choice(**overrides):
    base = dict(profile_id="cpct-hindi", layout_id="remington_gail_hindi", duration_seconds=None,
                backspace_allowed=True, passage_id=None)
    return SetupChoice(**{**base, **overrides})


def test_hindi_layouts_list_the_exam_layout_first():
    ids = [layout_id for layout_id, _ in layouts_for("hindi")]
    assert ids[0] == "remington_gail_hindi"
    assert "inscript_hindi" in ids


def test_english_uses_the_system_keyboard():
    assert layouts_for("english") == [(None, SYSTEM_KEYBOARD)]


def test_the_candidates_choices_override_the_profile():
    profile = effective_profile(PROFILES["cpct-hindi"], choice(duration_seconds=120, backspace_allowed=False))
    assert (profile.duration_seconds, profile.backspace_allowed) == (120, False)
    assert effective_profile(PROFILES["cpct-hindi"], choice()).duration_seconds == 900  # None keeps the default


def test_hindi_session_uses_the_chosen_layout_and_passage():
    session, name = build_session(PROFILES["cpct-hindi"], choice(passage_id="library-notice"))
    assert session.policy.keymap.id == "remington_gail_hindi"
    assert "Remington" in name
    assert session.source.startswith("नगर पुस्तकालय")


def test_english_session_has_no_keymap():
    session, name = build_session(
        PROFILES["cpct-english"], choice(profile_id="cpct-english", layout_id=None, passage_id="typing-practice")
    )
    assert session.policy.keymap is None
    assert name == SYSTEM_KEYBOARD
    assert session.source.startswith("Typing is a skill")


def test_random_source_is_long_enough_for_the_whole_exam():
    session, _ = build_session(PROFILES["cpct-hindi"], choice(), random.Random(1))
    assert len(session.source.split()) >= 15 * 40


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    save_settings({"profile_id": "cpct-hindi", "duration_seconds": 60}, path)
    assert load_settings(path) == {"profile_id": "cpct-hindi", "duration_seconds": 60}


def test_missing_or_damaged_settings_are_ignored(tmp_path):
    assert load_settings(tmp_path / "absent.json") == {}
    for content in ("{not json", "[1, 2]"):
        path = tmp_path / "bad.json"
        path.write_text(content, encoding="utf-8")
        assert load_settings(path) == {}


def test_failing_to_save_settings_is_silent(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    save_settings({"a": 1}, blocker / "settings.json")  # the parent "directory" is a file: must not raise
