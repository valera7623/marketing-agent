#!/usr/bin/env python3
"""Проверка доступа к Discord channel id из корня проекта."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))

if __name__ == "__main__":
    sys.argv[0] = str(AGENT / "check_discord_channels.py")
    runpy.run_path(str(AGENT / "check_discord_channels.py"), run_name="__main__")
