#!/usr/bin/env python3
"""Запуск outreach из корня проекта."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGENT = ROOT / "agent"
sys.path.insert(0, str(AGENT))

if __name__ == "__main__":
    sys.argv[0] = str(AGENT / "day_outreach.py")
    runpy.run_path(str(AGENT / "day_outreach.py"), run_name="__main__")
