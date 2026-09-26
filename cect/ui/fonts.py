"""Pick the exam font. The PRD asks for Mangal; Windows only ships it as an optional feature."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase

PREFERRED = {
    "hindi": ("Mangal", "Nirmala UI", "Aparajita", "Arial Unicode MS"),
    "english": ("Segoe UI", "Arial", "Calibri"),
}


def resolve_font(language: str) -> tuple[str, str]:
    """Return (family, note). `note` is empty when the first-choice font is in use, otherwise it says why not."""
    families = set(QFontDatabase.families())
    wanted = PREFERRED[language]
    for family in wanted:
        if family in families:
            note = "" if family == wanted[0] else f"{wanted[0]} is not installed; using {family}."
            return family, note
    fallback = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return fallback, f"{wanted[0]} is not installed; using {fallback}, which may not draw {language.title()} text correctly."
