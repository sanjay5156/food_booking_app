"""Path helpers that make the app work identically in three situations:
running from source (`python app.py`), and running as a PyInstaller-built
single-file .exe — where the running code lives in a temporary extraction
folder that disappears on exit, so writable data must live next to the
.exe instead."""

import os
import sys


def resource_path(relative_path):
    """Path to a bundled, read-only resource (templates/, static/).
    Works unmodified whether running from source or frozen into an .exe."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def app_data_dir():
    """Writable directory for the database, .env and logs — always next to
    the running .py file or .exe, so data survives between runs."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
