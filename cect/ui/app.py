"""Application entry point: setup screen, then the exam, then back to setup."""
from __future__ import annotations

import sys
from dataclasses import asdict

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication, QDialog

from ..profile import builtin_profiles
from ..settings import load_settings, save_settings
from ..setup import SetupChoice, build_session
from .exam_window import ExamWindow
from .fonts import resolve_font
from .setup_dialog import SetupDialog


class Controller(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.profiles = builtin_profiles()
        self.window: ExamWindow | None = None
        self.show_setup()

    def show_setup(self) -> None:
        dialog = SetupDialog(self.profiles, load_settings())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.window = None
            self.app.quit()
            return
        choice = dialog.choice()
        save_settings(asdict(choice))
        self._start(choice)

    def _start(self, choice: SetupChoice) -> None:
        profile = self.profiles[choice.profile_id]
        session, layout_name = build_session(profile, choice)
        family, note = resolve_font(session.profile.language)
        self.window = ExamWindow(session, layout_name, family, note)
        self.window.new_test.connect(self._new_test)
        self.window.show()

    def _new_test(self) -> None:
        if self.window is not None:
            self.window.close()
            self.window.deleteLater()
        self.show_setup()


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    controller = Controller(app)
    if controller.window is None:
        return 0  # the candidate quit from the setup screen
    return app.exec()
