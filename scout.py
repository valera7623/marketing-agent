#!/usr/bin/env python3
"""Скаут Discord URL из корня проекта."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))

if __name__ == "__main__":
    sys.argv[0] = str(AGENT / "scout_channel.py")
    runpy.run_path(str(AGENT / "scout_channel.py"), run_name="__main__")
