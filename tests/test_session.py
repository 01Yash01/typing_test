from dataclasses import replace

import pytest

from cect.entry import KeyInput
from cect.profile import builtin_profiles
from cect.session import FINISHED, READY, RUNNING, ExamSession

SOURCE = "the cat sat on the mat "
BASE = replace(builtin_profiles()["cpct-english"], duration_seconds=60)


class FakeClock:
    def __init__(self):
        self.now = 500.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


def make(clock, **overrides):
    return ExamSession(replace(BASE, **overrides), SOURCE, None, clock)


def type_text(session, text):
    for ch in text:
        session.key(KeyInput(text=ch))


BACKSPACE = KeyInput(action="backspace")


def test_typing_starts_the_countdown(clock):
    s = make(clock)
    assert s.phase == READY
    assert s.key(KeyInput(text="t")) is True
    assert (s.phase, s.text, s.timer.started) == (RUNNING, "t", True)


def test_ignored_keys_do_not_start_the_countdown(clock):
    s = make(clock)
    assert not s.key(KeyInput(text="\t"))
    assert not s.key(BACKSPACE)  # nothing to delete
    assert not s.key(KeyInput(text="c", shortcut=True))
    assert s.phase == READY


def test_start_button_mode_ignores_typing_until_started(clock):
    s = make(clock, timer_start="start_button")
    assert not s.key(KeyInput(text="t"))
    assert s.text == ""
    s.start()
    assert s.key(KeyInput(text="t"))
    assert s.phase == RUNNING


def test_submit_scores_the_text_and_stops_the_clock(clock):
    s = make(clock)
    type_text(s, SOURCE)
    clock.advance(30)
    result = s.submit()
    assert s.phase == FINISHED
    assert (result.accuracy, result.mistakes) == (100.0, 0)
    assert result.elapsed_seconds == 30
    assert result.net_wpm == round(len(SOURCE) / 5 / 0.5, 2)
    clock.advance(100)
    assert s.submit() is result  # the first result stands


def test_running_out_of_time_submits_exactly_once(clock):
    s = make(clock)
    type_text(s, "the cat")
    clock.advance(59.9)
    assert s.tick() is False
    clock.advance(0.2)
    assert s.tick() is True
    assert s.tick() is False
    assert s.result.elapsed_seconds == 60  # clamped to the exam duration
    assert s.phase == FINISHED


def test_a_key_arriving_after_time_is_up_is_refused_even_before_the_next_tick(clock):
    s = make(clock)
    type_text(s, "the")
    clock.advance(61)
    assert s.key(KeyInput(text="x")) is False
    assert s.text == "the" and s.phase == FINISHED


def test_keys_after_submit_are_ignored(clock):
    s = make(clock)
    type_text(s, "the")
    s.submit()
    assert not s.key(KeyInput(text="x"))
    assert s.text == "the"


def test_backspace_lock(clock):
    locked, free = make(clock, backspace_allowed=False), make(clock, backspace_allowed=True)
    for s in (locked, free):
        type_text(s, "cat")
        s.key(BACKSPACE)
    assert locked.text == "cat"
    assert free.text == "ca"


def test_submitting_without_typing_scores_zero(clock):
    r = make(clock).submit()
    assert (r.total_keystrokes, r.net_wpm, r.accuracy, r.passed) == (0, 0.0, 0.0, False)


def test_reset_gives_a_clean_second_attempt(clock):
    s = make(clock)
    type_text(s, "the cat")
    clock.advance(10)
    s.submit()
    s.reset()
    assert (s.phase, s.text, s.key_presses, s.result) == (READY, "", 0, None)
    assert s.timer.elapsed == 0
    type_text(s, "a")
    clock.advance(5)
    assert s.timer.elapsed == 5  # the countdown restarted from zero, at normal speed


def test_reset_can_swap_the_source_and_newline_rule(clock):
    s = make(clock)
    assert not s.key(KeyInput(action="enter"))
    s.reset("line one\nline two")
    assert s.key(KeyInput(action="enter"))
    assert s.text == "\n"


def test_key_presses_count_accepted_keys_including_backspace(clock):
    s = make(clock)
    type_text(s, "cat")
    s.key(BACKSPACE)
    s.key(KeyInput(text="\t"))
    assert s.key_presses == 4
