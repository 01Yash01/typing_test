# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the CPCT/CECT typing simulator.

Build with (from the project root, inside .venv):
    .venv\\Scripts\\pyinstaller packaging\\cect.spec --distpath dist --workpath build --noconfirm

Produces dist\\CECT-Typing-Simulator\\CECT-Typing-Simulator.exe as a --onedir build. onedir, not
--onefile: a onefile exe unpacks itself into a temp folder on every launch, which is slower to start
and more likely to be flagged by antivirus software than a plain folder of files.
"""
import pathlib

# PyInstaller execs this file rather than importing it, so __file__ is not set; SPEC is the builtin
# it injects instead, holding the path this spec file was invoked with.
ROOT = pathlib.Path(SPEC).resolve().parent.parent
APP_NAME = "CECT-Typing-Simulator"

# Package data that importlib.resources reads at runtime (cect/profile.py, cect/keymaps/__init__.py,
# cect/passages/__init__.py): PyInstaller only follows import statements, so JSON/Markdown data files
# have to be listed explicitly or the packaged app fails at startup with a FileNotFoundError.
datas = [
    (str(ROOT / "cect" / "profiles" / "*.json"), "cect/profiles"),
    (str(ROOT / "cect" / "keymaps" / "*.json"), "cect/keymaps"),
    (str(ROOT / "cect" / "keymaps" / "*.md"), "cect/keymaps"),
    (str(ROOT / "cect" / "passages" / "*.json"), "cect/passages"),
]

a = Analysis(
    [str(ROOT / "cect" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,  # a GUI app: no console window behind it
    disable_windowed_traceback=False,
)

COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=APP_NAME,
)
