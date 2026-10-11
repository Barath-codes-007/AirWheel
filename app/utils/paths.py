"""Filesystem locations used by AirWheel.

Normal mode stores data in the per-user Windows folder (%APPDATA%\\AirWheel).
Portable mode (a file named ``portable.flag`` next to the app/executable)
stores everything beside the application instead.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "AirWheel"


def app_root() -> Path:
    """Directory containing the app (source root, or the folder of the frozen exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def is_portable() -> bool:
    return (app_root() / "portable.flag").exists()


def data_dir() -> Path:
    """Writable directory for config, profiles and logs. Created if missing."""
    if is_portable():
        base = app_root() / "data"
    else:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / APP_NAME if appdata else Path.home() / f".{APP_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return data_dir() / "settings.json"


def profiles_dir() -> Path:
    p = data_dir() / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
