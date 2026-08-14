"""Пути проекта: все данные относительно корня marketing-agent."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT / "agent"
CONFIG_DIR = ROOT / "data"
DATA_DIR = ROOT / "data"
PLANS_DIR = ROOT / "plans"
DOCS_DIR = ROOT / "docs"
LOGS_DIR = ROOT / "logs"

CONFIG_PATH = DATA_DIR / "config.json"
LEADS_CSV = DATA_DIR / "outreach-leads.csv"
CONTACTED_USERS = DATA_DIR / "contacted_users.json"

DEFAULT_PLAN = PLANS_DIR / "day-01-2026-08-10.md"
ACCESSIBLE_PLAN = PLANS_DIR / "day-discord-accessible.md"

LIVE_LOG = LOGS_DIR / "outreach_live.log"
CHANNELS_REPORT = LOGS_DIR / "discord_channels_access.json"


def ensure_dirs() -> None:
    for d in (DATA_DIR, PLANS_DIR, DOCS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resolve_plan(name_or_path: str | Path) -> Path:
    """Ищет план в plans/ или принимает абсолютный/относительный путь."""
    p = Path(name_or_path)
    if p.is_file():
        return p
    candidate = PLANS_DIR / p.name
    if candidate.is_file():
        return candidate
    candidate = PLANS_DIR / name_or_path
    if candidate.is_file():
        return candidate
    return p
