"""One stylesheet for every screen, so the exam looks the same whatever theme Windows is using."""

STYLE = """
QWidget { color: #1e293b; }
QMainWindow, QDialog { background: #f1f5f9; }
#header { background: #1e3a8a; }
#header QLabel { color: white; font-weight: 600; }
#header QLabel#timer { color: #facc15; font-size: 18px; font-weight: 700; }
QLabel#notice { color: #b91c1c; font-size: 12px; }
QPlainTextEdit { background: #ffffff; color: #1e293b; border: 1px solid #94a3b8; padding: 8px; }
QPlainTextEdit#source { background: #f8fafc; }
QComboBox { background: #ffffff; border: 1px solid #94a3b8; border-radius: 4px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #dbeafe; selection-color: #1e293b; }
QTableWidget { background: #ffffff; color: #1e293b; gridline-color: #cbd5e1; }
QHeaderView::section { background: #f8fafc; color: #1e293b; border: 1px solid #cbd5e1; padding: 4px; }
QCheckBox { spacing: 8px; }
QPushButton { padding: 6px 18px; border: none; border-radius: 4px; background: #475569; color: white; }
QPushButton:disabled { background: #cbd5e1; }
QPushButton#submit { background: #16a34a; }
QPushButton#start { background: #2563eb; }
"""
