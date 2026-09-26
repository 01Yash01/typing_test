import os

# Run Qt without showing windows, so the UI tests work on any machine and never flash on screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
