"""
Where the app keeps its files, resolved per platform.

Deliberately no hardcoded ~/.config anywhere — a Windows build needs
%APPDATA%, and getting this wrong only shows up once the app is
packaged.
"""

import os
import sys
from pathlib import Path

from core import constants


def config_dir():
    """
    Returns the directory for settings, creating it if needed.

      Windows  %APPDATA%\\stream-buddy
      macOS    ~/Library/Application Support/stream-buddy
      Linux    $XDG_CONFIG_HOME/stream-buddy or ~/.config/stream-buddy
    """

    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"

    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"

    else:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else Path.home() / ".config"

    path = root / constants.APP_SLUG
    path.mkdir(parents=True, exist_ok=True)

    return path


def settings_file():
    return config_dir() / "settings.json"
