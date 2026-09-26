"""Remember the last setup between runs. A missing or damaged file is never an error."""
from __future__ import annotations

import json
import os
from pathlib import Path


def settings_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "cect" / "settings.json"


def load_settings(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(data: dict, path: Path | None = None) -> None:
    target = path or settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # remembering is a convenience; losing it must not stop an exam
