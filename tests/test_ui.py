"""Drives the real exam window with genuine key events (scan codes included), headless."""
import unicodedata
from dataclasses import replace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cect.history import HistoryEntry, load_history  # noqa: E402
from cect.keymaps import load_keymap  # noqa: E402
from cect.keymaps.typist import plan_keystrokes  # noqa: E402
from cect.profile import builtin_profiles  # noqa: E402
from cect.session import FINISHED, READY, RUNNING, ExamSession  # noqa: E402
from cect.ui.exam_window import ExamWindow  # noqa: E402
from cect.ui.fonts import resolve_font  # noqa: E402
from cect.ui.history_dialog import HistoryDialog  # noqa: E402
from cect.ui.mistakes_dialog import MistakesDialog  # noqa: E402
from cect.ui.setup_dialog import SetupDialog  # noqa: E402

GAIL = load_keymap("remington_gail_hindi")
SCAN = {label: scan for scan, label in GAIL.labels.items()}
MOD = Qt.KeyboardModifier


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture
def make_window(qapp, tmp_path):
    made = []
    # A history_path is always passed: without one, a submitted test would write to the real
    # per-user AppData history file, which must never happen from an automated test run.
    history_path = tmp_path / "history.json"

    def make(profile_id="cpct-hindi", source="कक कक कक ", keymap=GAIL, clock=None, **overrides):
        profile = replace(builtin_profiles()[profile_id], **overrides)
        session = ExamSession(profile, source, keymap, clock or FakeClock())
        window = ExamWindow(session, "test layout", "Arial", history_path=history_path)
        window.clock.stop()  # tests advance the clock and call _refresh() themselves
        made.append(window)
        return window

    make.history_path = history_path
    yield make
    for window in made:
        window.close()


def send(widget, key=Qt.Key.Key_A, mods=MOD.NoModifier, scan=0, text=""):
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, int(key), mods, scan, 0, 0, text))


def press_hindi(widget, key):
    scan, shift, altgr = key
    mods = MOD.NoModifier
    if shift:
        mods |= MOD.ShiftModifier
    if altgr:
        mods |= MOD.ControlModifier | MOD.AltModifier  # how Windows reports AltGr
    send(widget, mods=mods, scan=scan, text="")


def type_label(widget, label, shift=False):
    press_hindi(widget, (SCAN[label], shift, False))


def entry_text(window):
    return window.entry.toPlainText()


def test_a_virtual_typist_types_through_real_key_events_and_scores_100(make_window):
    source = "औषधि ओम आज 21/09/2026 को परीक्षा है। पेड़ ज़रूर (क्षत्रिय)"
    window = make_window(source=source)
    for key in plan_keystrokes(GAIL, source):
        press_hindi(window.entry, key)
    assert unicodedata.normalize("NFC", entry_text(window)) == unicodedata.normalize("NFC", source)
    window.submit_button.click()
    assert window.session.phase == FINISHED
    assert window.session.result.accuracy == 100.0
    assert window.score_dialog is not None


@pytest.mark.filterwarnings("ignore::DeprecationWarning")  # the simple QMouseEvent constructor is deprecated
def test_nothing_but_typing_can_change_the_text(make_window):
    window = make_window()
    type_label(window.entry, "d")
    type_label(window.entry, "d")
    before = entry_text(window)
    entry = window.entry

    mime = QMimeData()
    mime.setText("junk")
    entry.insertFromMimeData(mime)
    entry.paste()
    entry.cut()
    entry.undo()
    entry.selectAll()
    entry.cut()
    for key, mods, scan, text in [
        (Qt.Key.Key_Delete, MOD.NoModifier, 0x53, ""),
        (Qt.Key.Key_Left, MOD.NoModifier, 0x4B, ""),
        (Qt.Key.Key_Home, MOD.NoModifier, 0x47, ""),
        (Qt.Key.Key_A, MOD.ControlModifier, SCAN["a"], "\x01"),
        (Qt.Key.Key_V, MOD.ControlModifier, SCAN["v"], "\x16"),
        (Qt.Key.Key_Z, MOD.ControlModifier, SCAN["z"], "\x1a"),
        (Qt.Key.Key_Backspace, MOD.ControlModifier, 0x0E, "\x7f"),
        (Qt.Key.Key_Tab, MOD.NoModifier, 0x0F, "\t"),
        (Qt.Key.Key_Escape, MOD.NoModifier, 0x01, "\x1b"),
    ]:
        send(entry, key, mods, scan, text)
    click = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, MOD.NoModifier)
    QApplication.sendEvent(entry.viewport(), click)
    QApplication.sendEvent(entry, click)

    assert entry_text(window) == before == window.session.text
    assert not entry.textCursor().hasSelection()


def test_backspace_lock_follows_the_profile(make_window):
    locked, free = make_window(backspace_allowed=False), make_window(backspace_allowed=True)
    for window in (locked, free):
        type_label(window.entry, "d")
        type_label(window.entry, "d")
        send(window.entry, Qt.Key.Key_Backspace, scan=0x0E)
    assert entry_text(locked) == "कक"
    assert entry_text(free) == "क"


def test_english_window_types_what_the_system_keyboard_produces(make_window):
    window = make_window("cpct-english", source="the cat ", keymap=None)
    send(window.entry, Qt.Key.Key_T, text="t")
    send(window.entry, Qt.Key.Key_H, MOD.ShiftModifier, text="H")
    send(window.entry, Qt.Key.Key_Space, text=" ")
    send(window.entry, Qt.Key.Key_Tab, text="\t")
    assert entry_text(window) == "tH "


def test_running_out_of_time_shows_one_scorecard_and_locks_typing(make_window):
    clock = FakeClock()
    window = make_window(clock=clock, duration_seconds=60)
    type_label(window.entry, "d")
    assert window.session.phase == RUNNING
    clock.now += 61
    window._refresh()
    first = window.score_dialog
    window._refresh()
    assert first is not None and window.score_dialog is first  # exactly one scorecard
    assert window.session.phase == FINISHED
    assert not window.entry.isEnabled() and not window.submit_button.isEnabled()
    type_label(window.entry, "d")
    assert window.session.text == "क"


def test_start_button_mode_ignores_typing_until_started(make_window):
    window = make_window(timer_start="start_button")
    assert not window.start_button.isHidden()
    type_label(window.entry, "d")
    assert entry_text(window) == "" and window.session.phase == READY
    window.start_button.click()
    type_label(window.entry, "d")
    assert entry_text(window) == "क"


def test_reset_gives_a_clean_exam_and_a_fresh_scorecard_next_time(make_window):
    window = make_window()
    type_label(window.entry, "d")
    window.submit_button.click()
    first = window.score_dialog
    window.reset_button.click()
    assert (entry_text(window), window.session.phase) == ("", READY)
    assert window.entry.isEnabled() and window.submit_button.isEnabled()
    type_label(window.entry, "d")
    window.submit_button.click()
    assert window.score_dialog is not first


def test_buttons_never_take_keyboard_focus(make_window):
    window = make_window()
    for button in (window.start_button, window.reset_button, window.new_button, window.submit_button):
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_no_feedback_appears_while_typing(make_window):
    window = make_window(source="कक कक ")
    type_label(window.entry, "v")  # wrong: अ instead of क
    assert window.entry.extraSelections() == []
    assert window.source_view.toPlainText() == "कक कक "
    assert window.source_view.isReadOnly()


def test_the_countdown_is_shown(make_window):
    window = make_window(duration_seconds=90)
    assert window.timer_label.text() == "Time Remaining: 01:30"


# --- setup screen and fonts --------------------------------------------------------------------------

def test_setup_defaults_and_dependent_choices(qapp):
    dialog = SetupDialog(builtin_profiles())
    choice = dialog.choice()
    assert (choice.profile_id, choice.layout_id, choice.duration_seconds) == ("cpct-hindi", "remington_gail_hindi", None)
    assert choice.backspace_allowed and choice.passage_id is None
    dialog.profile_box.setCurrentIndex(dialog.profile_box.findData("cpct-english"))
    english = dialog.choice()
    assert english.layout_id is None  # the system keyboard
    assert dialog.passage_box.count() > 1


def test_setup_restores_the_previous_choices(qapp):
    saved = {"profile_id": "cpct-hindi", "layout_id": "inscript_hindi", "duration_seconds": 120,
             "backspace_allowed": False, "passage_id": "environment"}
    choice = SetupDialog(builtin_profiles(), saved).choice()
    assert (choice.layout_id, choice.duration_seconds, choice.backspace_allowed, choice.passage_id) == (
        "inscript_hindi", 120, False, "environment")


def test_setup_ignores_stale_saved_values(qapp):
    saved = {"profile_id": "gone", "layout_id": "gone", "duration_seconds": 7, "passage_id": "gone"}
    choice = SetupDialog(builtin_profiles(), saved).choice()
    assert choice.profile_id == "cpct-hindi" and choice.layout_id == "remington_gail_hindi"


def test_font_resolution_always_returns_a_family(qapp):
    for language in ("hindi", "english"):
        family, note = resolve_font(language)
        assert family and isinstance(note, str)


def test_history_button_opens_the_dialog_with_the_injected_loader(qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog, QPushButton

    opened = []
    monkeypatch.setattr(HistoryDialog, "exec", lambda self: opened.append(self) or QDialog.DialogCode.Accepted)
    entries = [HistoryEntry("a", 1.0, "p", "hindi", "l", 60, 10.0, 10.0, 90.0, True)]
    dialog = SetupDialog(builtin_profiles(), history_loader=lambda: entries)
    dialog._show_history()
    assert len(opened) == 1 and opened[0].table.rowCount() == 1
    assert isinstance(dialog.findChildren(QPushButton)[0], QPushButton)  # the button exists and is wired


# --- mistake review and history -----------------------------------------------------------------------

def test_submitting_shows_a_mistake_review_button_that_opens_the_correct_diff(make_window, monkeypatch):
    from PySide6.QtWidgets import QDialog, QPushButton

    opened = []
    monkeypatch.setattr(MistakesDialog, "exec", lambda self: opened.append(self) or QDialog.DialogCode.Accepted)
    window = make_window(source="कक कक कक ", keymap=GAIL)
    type_label(window.entry, "d")  # क: correct so far
    type_label(window.entry, "v")  # अ: makes the first word "कअ", which should have been "कक"
    window.submit_button.click()

    review_button = next(b for b in window.score_dialog.findChildren(QPushButton) if b.text() == "Review mistakes")
    review_button.click()
    assert len(opened) == 1
    dialog = opened[0]
    assert (dialog.table.rowCount(), dialog.table.item(0, 0).text()) == (1, "Wrong")
    assert (dialog.table.item(0, 1).text(), dialog.table.item(0, 2).text()) == ("कक", "कअ")


def test_mistakes_dialog_lists_only_non_correct_words():
    dialog = MistakesDialog("कक कक कक ", "कक अक कक ")
    try:
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, 0).text() == "Wrong"
        assert dialog.table.item(0, 1).text() == "कक"
        assert dialog.table.item(0, 2).text() == "अक"
    finally:
        dialog.deleteLater()


def test_mistakes_dialog_says_so_when_there_are_none():
    dialog = MistakesDialog("क क", "क क")
    try:
        assert dialog.table.rowCount() == 0
        assert "No mistakes" in dialog.summary.text()
    finally:
        dialog.deleteLater()


def test_submitting_appends_one_history_entry(make_window):
    window = make_window()
    assert load_history(make_window.history_path) == []
    type_label(window.entry, "d")
    window.submit_button.click()
    entries = load_history(make_window.history_path)
    assert len(entries) == 1
    e = entries[0]
    assert (e.profile_name, e.layout_name, e.language) == (window.session.profile.name, "test layout", "hindi")
    assert e.net_wpm == window.session.result.net_wpm


def test_submitting_twice_from_two_windows_appends_two_entries(make_window):
    for _ in range(2):
        w = make_window()
        type_label(w.entry, "d")
        w.submit_button.click()
    assert len(load_history(make_window.history_path)) == 2


def test_history_dialog_lists_entries_most_recent_first():
    old = HistoryEntry("a", 100.0, "CPCT Hindi typing", "hindi", "GAIL", 900, 10.0, 12.0, 90.0, False)
    new = HistoryEntry("b", 200.0, "CPCT Hindi typing", "hindi", "GAIL", 900, 25.0, 26.0, 96.0, True)
    dialog = HistoryDialog([old, new])
    try:
        assert dialog.table.rowCount() == 2
        assert dialog.table.item(0, 6).text() == "Passed"  # the newer entry (timestamp 200) sorts first
        assert dialog.table.item(1, 6).text() == "Not qualified"
    finally:
        dialog.deleteLater()


def test_history_dialog_with_no_entries_says_so():
    dialog = HistoryDialog([])
    try:
        assert "No tests recorded" in dialog.summary.text()
    finally:
        dialog.deleteLater()


# --- launcher flow -----------------------------------------------------------------------------------

@pytest.fixture
def launcher(qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import cect.ui.app as app_module

    saved = []
    monkeypatch.setattr(app_module, "load_settings", lambda: {})
    monkeypatch.setattr(app_module, "save_settings", saved.append)
    answers = {"result": QDialog.DialogCode.Accepted}
    monkeypatch.setattr(app_module.SetupDialog, "exec", lambda self: answers["result"])
    return app_module, saved, answers


def test_accepting_the_setup_screen_starts_a_hindi_exam_and_remembers_the_choice(qapp, launcher):
    app_module, saved, _ = launcher
    controller = app_module.Controller(qapp)
    try:
        assert controller.window.session.profile.language == "hindi"
        assert controller.window.session.policy.keymap.id == "remington_gail_hindi"
        assert saved and saved[0]["profile_id"] == "cpct-hindi"
    finally:
        controller.window.close()


def test_quitting_from_the_setup_screen_opens_no_exam(qapp, launcher):
    from PySide6.QtWidgets import QDialog

    app_module, saved, answers = launcher
    answers["result"] = QDialog.DialogCode.Rejected
    assert app_module.Controller(qapp).window is None
    assert saved == []


def test_new_test_replaces_the_exam_window_with_a_fresh_one(qapp, launcher):
    app_module, _, _ = launcher
    controller = app_module.Controller(qapp)
    first = controller.window
    first.new_test.emit()
    try:
        assert controller.window is not first
    finally:
        controller.window.close()
