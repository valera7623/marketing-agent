"""Скаут Discord-канала по URL: найти сигнальные посты и черновики outreach.

Пример:
  python scout.py "https://discord.com/channels/GUILD/CHANNEL"
  python scout.py "https://discord.com/channels/GUILD/CHANNEL" --limit 5 --draft
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from contacted_store import ContactedStore
from discord_api import DiscordAPI, extract_game_name, message_to_post
from local_llm import Config, ask_ollama
from outreach_plan import build_personalize_prompt, fill_template, parse_outreach_plan
from paths import (
    CONFIG_PATH,
    CONTACTED_USERS,
    DEFAULT_PLAN,
    LOGS_DIR,
    ensure_dirs,
    resolve_plan,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Группы сигналов из ручного плана
SIGNAL_GROUPS = {
    "loc": [
        "localiz",
        "localisation",
        "localization",
        "translate",
        "translation",
        "перевод",
        "локализ",
        "i18n",
        "l10n",
        "мультиязыч",
        "multilang",
        "language pack",
    ],
    "steam_csv": [
        "steam",
        "en-only",
        "en only",
        "english only",
        "csv",
        "wishlist",
        "key,source",
        "strings",
    ],
    "release": [
        "release",
        "released",
        "showcase",
        "launch",
        "vertical slice",
        "demo",
        "релиз",
        "анонс",
        "indie",
        "godot",
        "unity",
    ],
}

DM_TEMPLATE = """Hey — saw your {game}. LocForge localizes indie CSV in one evening (glossary + UI length QA + Unity/Godot export).

Happy to run a free pilot on your strings (RU/ES/DE). If it helps and you are ok with it, we can feature the game on the case page.

Link: https://gameforge.website/en/locforge?utm_source=discord&utm_medium=dm&utm_campaign=lf_en&from=locforge
Or just reply with a CSV."""

COMMENT_TEMPLATE = """If you already have key,source CSV, LocForge does glossary + length QA + Unity/Godot export without a bureau — useful before Steam multilingual. Happy to pilot for free if you DM a sample.

https://gameforge.website/en/locforge?utm_source=discord&utm_medium=comment&utm_campaign=lf_en&from=locforge"""


def parse_discord_url(url: str) -> Dict[str, str]:
    """
    https://discord.com/channels/{guild_id}/{channel_id}
    https://discord.com/channels/{guild_id}/{channel_id}/{message_id}
    """
    raw = (url or "").strip().strip("<>")
    parsed = urlparse(raw)
    if "discord.com" not in parsed.netloc and "discordapp.com" not in parsed.netloc:
        raise ValueError("Это не Discord URL (ожидается discord.com/channels/...)")

    parts = [p for p in parsed.path.split("/") if p]
    # channels / guild / channel [/ message]
    if len(parts) < 3 or parts[0] != "channels":
        raise ValueError(
            "Неверный формат. Нужно: https://discord.com/channels/GUILD_ID/CHANNEL_ID"
        )

    guild_id = parts[1]
    channel_id = parts[2]
    message_id = parts[3] if len(parts) > 3 else ""
    return {
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": message_id,
        "url": raw,
    }


def score_content(content: str) -> Tuple[int, List[str], List[str]]:
    """Очки = число групп сигналов, которые сработали."""
    lowered = (content or "").lower()
    hits: List[str] = []
    matched_groups: List[str] = []
    for group, words in SIGNAL_GROUPS.items():
        group_hits = [w for w in words if w in lowered]
        if group_hits:
            matched_groups.append(group)
            hits.extend(group_hits[:3])
    return len(matched_groups), matched_groups, hits


def pick_template(matched_groups: List[str], prefer: str = "auto") -> Tuple[str, str]:
    """Возвращает (template_name, template_text)."""
    if prefer == "dm":
        return "dm_en", DM_TEMPLATE
    if prefer == "comment":
        return "comment_en", COMMENT_TEMPLATE
    # loc-вопрос → comment; showcase/release → dm
    if "loc" in matched_groups and "release" not in matched_groups:
        return "comment_en", COMMENT_TEMPLATE
    return "dm_en", DM_TEMPLATE


def load_plan_templates(plan_path: Path) -> Dict[str, str]:
    touches = parse_outreach_plan(plan_path)
    out: Dict[str, str] = {}
    for t in touches:
        key = t.get("template") or ""
        if key and key not in out and t.get("template_text"):
            out[key] = t["template_text"]
    return out


async def scout(
    url: str,
    *,
    history_limit: int = 50,
    top: int = 5,
    draft: bool = True,
    template_prefer: str = "auto",
    plan_file: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_dirs()
    meta = parse_discord_url(url)
    channel_id = meta["channel_id"]

    config = Config(str(CONFIG_PATH))
    token = config.get("discord_token") or (config.get("discord") or {}).get("token")
    if not token:
        raise RuntimeError("Нет discord_token в data/config.json")

    discord_cfg = config.get("discord") or {}
    contacted = ContactedStore(
        path=CONTACTED_USERS,
        cooldown_days=int(discord_cfg.get("cooldown_days", 7)),
    )
    skip_ids = contacted.recently_contacted_ids()

    plan_templates = load_plan_templates(resolve_plan(plan_file or DEFAULT_PLAN))

    api = DiscordAPI(token)
    await api.connect()
    bot_id = str((api.bot_user or {}).get("id", ""))
    channel_name = channel_id
    guild_id = meta["guild_id"]
    messages: List[Dict[str, Any]] = []
    try:
        ch = await api._request("GET", f"/channels/{channel_id}")
        channel_name = ch.get("name") or channel_id
        guild_id = str(ch.get("guild_id") or meta["guild_id"])
        messages = await api.get_channel_messages(channel_id, limit=history_limit)
    finally:
        await api.close()

    candidates: List[Dict[str, Any]] = []

    for msg in messages:
        author = msg.get("author") or {}
        author_id = str(author.get("id", ""))
        if author.get("bot") or author_id == bot_id:
            continue
        if author_id in skip_ids:
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        score, groups, hits = score_content(content)
        if score <= 0:
            continue

        post = message_to_post(msg, channel_id)
        post["guild_id"] = guild_id
        post["url"] = f"https://discord.com/channels/{guild_id}/{channel_id}/{msg.get('id')}"
        post["score"] = score
        post["signal_groups"] = groups
        post["signal_hits"] = hits
        if meta["message_id"] and str(msg.get("id")) == meta["message_id"]:
            post["score"] += 10
            post["from_url_message"] = True
        candidates.append(post)

    candidates.sort(key=lambda p: (p.get("score", 0), p.get("message_id", "")), reverse=True)
    top_posts = candidates[:top]

    drafts: List[Dict[str, Any]] = []
    for post in top_posts:
        template_name, template_text = pick_template(post.get("signal_groups") or [], template_prefer)
        if template_name in plan_templates:
            template_text = plan_templates[template_name]

        game_name = post.get("game_name") or "your game"
        filled = fill_template(template_text, game_name)
        draft_text = filled

        if draft:
            touch = {
                "channel": "Discord",
                "context": f"#{channel_name}",
                "language": "EN" if "en" in template_name else "RU",
                "template": template_name,
            }
            prompt = build_personalize_prompt(filled, game_name, touch)
            prompt += f"\n\nФрагмент поста разработчика:\n{(post.get('content') or '')[:240]}\n"
            try:
                personalized = await ask_ollama(prompt, config.get("llm"))
                if personalized:
                    draft_text = personalized
                    if "gameforge.website" not in draft_text:
                        draft_text += (
                            "\n\nhttps://gameforge.website/en/locforge"
                            "?utm_source=discord&utm_medium=dm&utm_campaign=lf_en&from=locforge"
                        )
            except Exception as e:
                draft_text = filled + f"\n\n[LLM fallback: {e}]"

        drafts.append(
            {
                "author": post.get("author"),
                "author_id": post.get("author_id"),
                "game_name": game_name,
                "score": post.get("score"),
                "signals": post.get("signal_groups"),
                "hits": post.get("signal_hits"),
                "post_url": post.get("url"),
                "post_content": post.get("content"),
                "template": template_name,
                "draft": draft_text,
                "action": "DM" if template_name.startswith("dm") else "REPLY",
            }
        )

    return {
        "scouted_at": datetime.now().isoformat(),
        "source_url": meta["url"],
        "guild_id": guild_id,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "scanned": len(messages),
        "matched": len(candidates),
        "drafts": drafts,
    }


def render_report(result: Dict[str, Any]) -> str:
    lines = [
        f"# Scout report — {result.get('channel_name')} — {result.get('scouted_at', '')[:19]}",
        "",
        f"- URL: {result.get('source_url')}",
        f"- Channel: #{result.get('channel_name')} (`{result.get('channel_id')}`)",
        f"- Scanned: {result.get('scanned')} msgs · matched: {result.get('matched')}",
        "",
    ]
    drafts = result.get("drafts") or []
    if not drafts:
        lines.append("**Сигнальных постов не найдено.**")
        lines.append(
            "Попробуйте другой канал / больший `--history`, или скиньте URL конкретного сообщения."
        )
        return "\n".join(lines)

    for i, d in enumerate(drafts, 1):
        lines.append(f"## {i}. @{d.get('author')} · {d.get('game_name')} · score={d.get('score')}")
        lines.append("")
        lines.append(f"- Action: **{d.get('action')}** (`{d.get('template')}`)")
        lines.append(f"- Signals: {', '.join(d.get('signals') or [])}")
        lines.append(f"- Hits: {', '.join(d.get('hits') or [])}")
        lines.append(f"- Post: {d.get('post_url')}")
        lines.append("")
        lines.append("**Post:**")
        lines.append("```")
        lines.append((d.get("post_content") or "")[:500])
        lines.append("```")
        lines.append("")
        lines.append("**Draft to send:**")
        lines.append("```")
        lines.append(d.get("draft") or "")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("Дальше: скопируйте draft → Discord (Reply или DM) → отметьте в `data/outreach-leads.csv`.")
    return "\n".join(lines)


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Scout Discord channel URL for LocForge signals")
    parser.add_argument("url", help="Discord channel/message URL")
    parser.add_argument("--history", type=int, default=50, help="Сколько последних сообщений читать")
    parser.add_argument("--limit", type=int, default=5, help="Сколько топ-постов в отчёт")
    parser.add_argument("--no-draft", action="store_true", help="Не генерировать текст через Ollama")
    parser.add_argument(
        "--template",
        choices=["auto", "dm", "comment"],
        default="auto",
        help="Какой шаблон предпочесть",
    )
    parser.add_argument("--plan", default=None, help="План из plans/ для шаблонов")
    args = parser.parse_args()

    try:
        result = await scout(
            args.url,
            history_limit=args.history,
            top=args.limit,
            draft=not args.no_draft,
            template_prefer=args.template,
            plan_file=args.plan,
        )
    except Exception as e:
        print(f"❌ Scout failed: {e}")
        sys.exit(1)

    report = render_report(result)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_json = LOGS_DIR / f"scout_{stamp}.json"
    out_md = LOGS_DIR / f"scout_{stamp}.md"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n📁 JSON: {out_json}")
    print(f"📄 MD:   {out_md}")


if __name__ == "__main__":
    asyncio.run(amain())
