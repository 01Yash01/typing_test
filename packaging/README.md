# Building the Windows package

```
.venv\Scripts\pyinstaller packaging\cect.spec --distpath dist --workpath build --noconfirm
```

Produces `dist\CECT-Typing-Simulator\` (a `--onedir` build, not `--onefile`: a onefile exe unpacks
itself into a temp folder on every launch, which is slower to start and more likely to be flagged by
antivirus software). Ship the whole `CECT-Typing-Simulator` folder, or `dist\CECT-Typing-Simulator.zip`.
`build\` is intermediate and can be deleted; only `dist\` is needed to run or distribute the app.

## What's been verified

- The built `.exe` launches as a standalone process (no project folder, no venv on `PATH`, run from
  `C:\Windows` as the working directory) and its setup screen renders correctly with real data pulled
  from the bundled profile, keymap and passage JSON files — proving PyInstaller's `datas` list is
  correct and `importlib.resources` finds everything in the frozen build.
- No crash traceback file was written (PyInstaller writes one next to the `.exe` on an unhandled
  exception in a windowed app), and process exit was clean once closed.
- The Qt platform plugin (`qwindows.dll`) and the VC++ runtime DLLs (`VCRUNTIME140.dll`,
  `VCRUNTIME140_1.dll`) are present in `_internal\`, which are the two most common reasons a frozen Qt
  app fails to start on a machine without Python or Visual Studio installed.
- All 292 automated tests pass against the same source tree the build was made from.

## What has *not* been verified

- **Running on an actual second machine.** Everything above was checked on the machine that built it,
  which already has the VC++ redistributable and other prerequisites installed from unrelated software.
  A machine that has never had *any* Visual C++ app installed is the real test.
- **High-DPI displays (125–150% scaling).** Not checked on a scaled display.
- **Antivirus behaviour.** PyInstaller-built executables are sometimes flagged by antivirus/SmartScreen
  as unrecognized software, even when clean, because they are unsigned. Code-signing the `.exe` would
  avoid this but requires a certificate, which is a decision for you, not something to do silently.
- **The full exam flow (Start → type → Submit) inside the frozen build specifically**, rather than the
  setup screen alone — automating a real click-through against a live window on this machine proved
  unreliable (global synthetic key/focus events landed on the wrong window). The exam window, entry
  pane, scoring, timer, mistake review and history are unchanged frozen code already covered by the 292
  tests that run directly against the source; only the *packaging* of that code was the open question
  here, and that is what was checked above.
