"""Проверка доступа бота ко всем channel id из data/config.json.

Запуск из корня проекта:
  python check_channels.py
  python check_channels.py --write-plan
  python check_channels.py --write-plan --prune-config
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from paths import (
    ACCESSIBLE_PLAN,
    CHANNELS_REPORT,
    CONFIG_PATH,
    ensure_dirs,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

API = "https://discord.com/api/v10"
REPORT_PATH = CHANNELS_REPORT
PLAN_PATH = ACCESSIBLE_PLAN

# Имена каналов → шаблон касания для урезанного плана
CHANNEL_TOUCH_HINTS = {
    "godot-announce": ("dm_en", "Godot #godot-announce", "после анонса Godot-проекта / релиза"),
    "discord-announce": ("comment_en", "Discord #discord-announce", "публичный анонс / вопрос про лок"),
    "incoming-announce": ("dm_en", "Discord #incoming-announce", "входящий анонс инди-проекта"),
    "announcements": ("dm_en", "Discord #announcements", "анонс игры / Steam"),
    "startboard": ("dm_en", "Discord #starboard", "засветившийся пост (starboard)"),
    "starboard": ("dm_en", "Discord #starboard", "засветившийся пост (starboard)"),
    "announcements-unity": ("dm_en", "Unity #announcements-unity", "Unity-анонс / showcase"),
    "insiders": ("dm_en", "Discord #insiders", "инсайдерский анонс / WIP"),
    "udc-jam-news": ("dm_en", "Discord #udc-jam-news", "jam / meetup новости"),
}


def load_config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def list_bot_guild_text_channels(session: requests.Session) -> List[Tuple[str, str]]:
    """Каналы на серверах, где бот уже состоит (реальный доступ)."""
    entries: List[Tuple[str, str]] = []
    seen = set()
    try:
        guilds = session.get(f"{API}/users/@me/guilds", timeout=20)
        guilds.raise_for_status()
    except Exception as e:
        print(f"⚠️ Не удалось получить guilds бота: {e}")
        return entries

    for g in guilds.json():
        gid = g.get("id")
        gname = g.get("name") or gid
        try:
            chans = session.get(f"{API}/guilds/{gid}/channels", timeout=20)
            if chans.status_code != 200:
                print(f"⚠️ guild {gname}: channels {chans.status_code}")
                continue
            for ch in chans.json():
                # 0 = text, 5 = announcement
                if ch.get("type") not in (0, 5):
                    continue
                cid = str(ch.get("id"))
                if cid in seen:
                    continue
                seen.add(cid)
                label = f"{gname}/#{ch.get('name')}"
                entries.append((label, cid))
        except Exception as e:
            print(f"⚠️ guild {gname}: {e}")
    return entries


def collect_channel_entries(cfg: Dict[str, Any], session: requests.Session | None = None) -> List[Tuple[str, str]]:
    """Уникальные (label, channel_id) из конфига + опционально с серверов бота."""
    discord_cfg = cfg.get("discord") or {}
    channel_map = discord_cfg.get("channel_map") or {}
    seen = set()
    entries: List[Tuple[str, str]] = []

    preferred = [
        "godot-announce",
        "discord-announce",
        "incoming-announce",
        "announcements",
        "startboard",
        "starboard",
        "announcements-unity",
        "insiders",
        "udc-jam-news",
    ]
    for key in preferred:
        cid = channel_map.get(key)
        if cid and str(cid) not in seen:
            seen.add(str(cid))
            entries.append((key, str(cid)))

    for key, cid in channel_map.items():
        cid = str(cid)
        if cid not in seen:
            seen.add(cid)
            entries.append((str(key), cid))

    for cid in discord_cfg.get("channels") or cfg.get("discord_channels") or []:
        cid = str(cid)
        if cid not in seen:
            seen.add(cid)
            entries.append((cid, cid))

    # Каналы серверов, где бот уже есть
    if session is not None:
        for label, cid in list_bot_guild_text_channels(session):
            if cid not in seen:
                seen.add(cid)
                entries.append((label, cid))

    return entries


def check_channel(session: requests.Session, channel_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "channel_id": channel_id,
        "ok": False,
        "name": None,
        "type": None,
        "guild_id": None,
        "can_read_history": False,
        "recent_humans": 0,
        "error": None,
    }
    try:
        r = session.get(f"{API}/channels/{channel_id}", timeout=20)
        if r.status_code != 200:
            result["error"] = f"{r.status_code}: {r.text[:200]}"
            return result
        data = r.json()
        result["name"] = data.get("name")
        result["type"] = data.get("type")
        result["guild_id"] = str(data.get("guild_id") or "")
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)
        return result

    try:
        h = session.get(
            f"{API}/channels/{channel_id}/messages",
            params={"limit": 20},
            timeout=20,
        )
        if h.status_code == 200:
            result["can_read_history"] = True
            humans = 0
            for msg in h.json():
                author = msg.get("author") or {}
                if not author.get("bot") and (msg.get("content") or "").strip():
                    humans += 1
            result["recent_humans"] = humans
        else:
            result["error"] = f"history {h.status_code}: {h.text[:200]}"
    except Exception as e:
        result["error"] = f"history: {e}"

    return result


def build_plan(ok_rows: List[Dict[str, Any]], label_by_id: Dict[str, str]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Outreach Discord (accessible only) — {today}",
        "",
        "**Goal:** LocForge free pilot · только каналы, куда бот реально имеет доступ  ",
        f"**Cadence:** {len(ok_rows)} Discord touches · auto DM  ",
        "**Rules:** value first · DM only after public intent · skip if already contacted 7d  ",
        "**Generated by:** `check_discord_channels.py --write-plan`",
        "",
        "| # | id | Channel | Template | Target | channel_id |",
        "|---|----|---------|----------|--------|------------|",
    ]

    touches_md = []
    for i, row in enumerate(ok_rows, 1):
        cid = row["channel_id"]
        label = label_by_id.get(cid, row.get("name") or cid)
        hint = CHANNEL_TOUCH_HINTS.get(label) or (
            "dm_en",
            f"Discord #{row.get('name') or label}",
            "после релевантного поста про лок / Steam / CSV",
        )
        template, context, when = hint
        touch_id = str(100 + i)
        lines.append(
            f"| {i} | {touch_id} | Discord | {template} | {context} | `{cid}` |"
        )

        template_body = (
            "Hey — saw your {game} in #"
            + (row.get("name") or label)
            + ". LocForge localizes indie CSV in one evening (glossary + UI length QA + Unity/Godot export).\n\n"
            "Happy to run a free pilot on your strings (RU/ES/DE). If it helps and you are ok with it, "
            "we can feature the game on the case page.\n\n"
            "Link: https://gameforge.website/en/locforge?utm_source=discord&utm_medium=dm&utm_campaign=lf_en&from=locforge\n"
            "Or just reply with a CSV."
            if template.startswith("dm")
            else (
                "If you already have key,source CSV, LocForge does glossary + length QA + Unity/Godot export "
                "without a bureau — useful before Steam multilingual. Happy to pilot for free if you DM a sample.\n\n"
                "https://gameforge.website/en/locforge?utm_source=discord&utm_medium=comment&utm_campaign=lf_en&from=locforge"
            )
        )

        touches_md.append(
            f"""
## {i} · Discord · {context} · `{template}` · id={touch_id}

**When:** {when}.  
**Channel id:** `{cid}`

```
{template_body}
```

- [ ] Sent

---
""".strip()
        )

    lines.append("")
    lines.append(f"Mix: Discord ×{len(ok_rows)} · accessible only")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("\n\n".join(touches_md))
    lines.append("")
    lines.append("## End-of-day log")
    lines.append("")
    lines.append("| id | Actual person / thread | reply (yes/maybe/no) | notes |")
    lines.append("|----|------------------------|----------------------|-------|")
    for i, _ in enumerate(ok_rows, 1):
        lines.append(f"| {100 + i} | | | |")
    lines.append("")
    lines.append(
        "**Pilot intake:** CSV `key,source` → email `gameforge.website@yandex.ru` "
        "subject `LocForge pilot`"
    )
    lines.append("")
    return "\n".join(lines)


def prune_config(cfg: Dict[str, Any], ok_ids: List[str], label_by_id: Dict[str, str], fail_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    discord_cfg = dict(cfg.get("discord") or {})
    old_map = discord_cfg.get("channel_map") or {}
    new_map = {}
    for key, cid in old_map.items():
        if str(cid) in ok_ids:
            new_map[key] = str(cid)
    for cid in ok_ids:
        label = label_by_id.get(cid, cid)
        new_map[label] = cid
        # короткие ключи по имени канала
        name = None
        for row in fail_rows:
            pass
        short = label.split("/#")[-1] if "/#" in label else label
        new_map[short] = cid

    pending = dict(discord_cfg.get("channel_map_pending") or {})
    for row in fail_rows:
        pending[row.get("label") or row["channel_id"]] = row["channel_id"]

    discord_cfg["channel_map"] = new_map
    discord_cfg["channel_map_pending"] = pending
    discord_cfg["default_channel_id"] = ok_ids[0] if ok_ids else discord_cfg.get("default_channel_id")
    cfg["discord"] = discord_cfg
    cfg["discord_channels"] = list(ok_ids)
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Discord channel access for LocForge bot")
    parser.add_argument("--write-plan", action="store_true", help=f"Пишет {PLAN_PATH}")
    parser.add_argument(
        "--prune-config",
        action="store_true",
        help="Оставляет в config.json только доступные channel id",
    )
    args = parser.parse_args()
    ensure_dirs()

    cfg = load_config()
    token = cfg.get("discord_token") or (cfg.get("discord") or {}).get("token")
    if not token:
        print("❌ Нет discord_token в config.json")
        sys.exit(1)

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bot {token}",
            "User-Agent": "LocForgeOutreachBot (channel-check, 1.0)",
        }
    )

    entries = collect_channel_entries(cfg, session=session)
    print(f"Проверяю {len(entries)} уникальных channel id…\n")
    rows = []
    label_by_id: Dict[str, str] = {}
    for label, cid in entries:
        label_by_id.setdefault(cid, label)
        info = check_channel(session, cid)
        info["label"] = label
        rows.append(info)
        status = "OK" if info["ok"] and info["can_read_history"] else "FAIL"
        name = info.get("name") or "?"
        humans = info.get("recent_humans", 0)
        err = info.get("error") or ""
        print(f"[{status}] #{name} ({label}) id={cid} humans~{humans} {err}")

    ok_rows = [r for r in rows if r.get("ok") and r.get("can_read_history")]
    fail_rows = [r for r in rows if r not in ok_rows]

    report = {
        "checked_at": datetime.now().isoformat(),
        "ok_count": len(ok_rows),
        "fail_count": len(fail_rows),
        "ok": ok_rows,
        "fail": fail_rows,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 50)
    print(f"Доступны: {len(ok_rows)} / {len(rows)}")
    print(f"Отчёт: {REPORT_PATH}")

    if args.write_plan:
        if not ok_rows:
            print("⚠️ Нет доступных каналов — план не создан")
        else:
            plan = build_plan(ok_rows, label_by_id)
            PLAN_PATH.write_text(plan, encoding="utf-8")
            print(f"План: {PLAN_PATH} ({len(ok_rows)} касаний)")

    if args.prune_config:
        ok_ids = [r["channel_id"] for r in ok_rows]
        if not ok_ids:
            print("⚠️ prune-config пропущен: нет доступных каналов")
        else:
            new_cfg = prune_config(cfg, ok_ids, label_by_id, fail_rows)
            CONFIG_PATH.write_text(
                json.dumps(new_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"config.json обновлён: {len(ok_ids)} каналов")

    if not ok_rows:
        print(
            "\nПодсказка: пригласите бота на сервера (OAuth2 URL Generator → bot + "
            "View Channel + Read Message History) и включите Message Content Intent."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
