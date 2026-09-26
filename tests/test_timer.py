import pytest

from cect.timer import ExamTimer


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def timer(clock):
    return ExamTimer(900, clock=clock)


def test_idle_timer(timer):
    assert (timer.elapsed, timer.remaining) == (0.0, 900.0)
    assert not (timer.started or timer.running or timer.finished or timer.expired)
    assert timer.display() == "15:00"


def test_counts_down(timer, clock):
    timer.start()
    clock.advance(61.5)
    assert timer.elapsed == 61.5
    assert timer.remaining == 838.5
    assert timer.running
    assert timer.display() == "13:59"


def test_display_rounds_up_so_zero_means_out_of_time(timer, clock):
    timer.start()
    clock.advance(0.4)
    assert timer.display() == "15:00"
    clock.advance(0.7)
    assert timer.display() == "14:59"
    clock.advance(898.0)
    assert timer.display() == "00:01"
    clock.advance(0.9)
    assert timer.display() == "00:00" and timer.expired


def test_expiry_clamps_elapsed_to_the_duration(timer, clock):
    timer.start()
    clock.advance(1000)
    assert timer.expired and timer.finished and not timer.running
    assert (timer.elapsed, timer.remaining) == (900.0, 0.0)


def test_stop_freezes_elapsed_time(timer, clock):
    timer.start()
    clock.advance(30)
    timer.stop()
    clock.advance(500)
    assert timer.elapsed == 30
    assert timer.finished and not timer.expired


def test_stop_after_expiry_keeps_the_full_duration(timer, clock):
    timer.start()
    clock.advance(2000)
    timer.stop()
    assert timer.elapsed == 900


def test_stop_before_start_does_nothing(timer, clock):
    timer.stop()
    assert not timer.finished
    timer.start()
    clock.advance(5)
    assert timer.elapsed == 5


def test_start_is_idempotent(timer, clock):
    timer.start()
    clock.advance(10)
    timer.start()  # e.g. every keystroke calling start(): must not restart the clock
    clock.advance(5)
    assert timer.elapsed == 15


def test_reset_then_immediate_restart_runs_at_normal_speed(timer, clock):
    # The prototype's Reset-then-type-within-a-second race made the countdown run twice as fast.
    timer.start()
    clock.advance(0.3)
    timer.reset()
    timer.start()
    clock.advance(5)
    assert timer.elapsed == 5


@pytest.mark.parametrize("duration", [0, -5])
def test_rejects_non_positive_duration(duration):
    with pytest.raises(ValueError):
        ExamTimer(duration)
