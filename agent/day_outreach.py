import argparse
import asyncio
import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from contacted_store import ContactedStore
from discord_api import (
    DiscordAPI,
    find_discord_posts,
    make_seed_post,
    resolve_discord_channel_id,
)
from local_llm import Config, ask_ollama
from outreach_plan import build_personalize_prompt, fill_template, parse_outreach_plan
from paths import (
    CONFIG_PATH,
    CONTACTED_USERS,
    DEFAULT_PLAN,
    LEADS_CSV,
    LIVE_LOG,
    LOGS_DIR,
    ensure_dirs,
    resolve_plan,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CSV_HEADERS = [
    "id",
    "status",
    "sent_at",
    "author",
    "author_id",
    "game_name",
    "reply",
    "reply_at",
    "notes",
]


def live_log(line: str) -> None:
    """Печать + append в logs/outreach_live.log в реальном времени."""
    ensure_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{stamp}] {line}"
    print(text)
    with LIVE_LOG.open("a", encoding="utf-8") as f:
        f.write(text + "\n")
        f.flush()


class OutreachDayAutomation:
    def __init__(
        self,
        plan_file: str | Path | None = None,
        config_path: str | Path | None = None,
    ):
        ensure_dirs()
        self.plan_file = resolve_plan(plan_file or DEFAULT_PLAN)
        self.config = Config(str(config_path or CONFIG_PATH))
        self.touches = parse_outreach_plan(self.plan_file)
        self.discord: Optional[DiscordAPI] = None
        self.sent_log = []
        discord_cfg = self._discord_cfg()
        contacted_name = discord_cfg.get("contacted_file") or "contacted_users.json"
        contacted_path = Path(contacted_name)
        if not contacted_path.is_absolute():
            contacted_path = (
                CONTACTED_USERS
                if contacted_name == "contacted_users.json"
                else (CONFIG_PATH.parent / contacted_name)
            )
        self.contacted = ContactedStore(
            path=contacted_path,
            cooldown_days=int(discord_cfg.get("cooldown_days", 7)),
        )

    def _discord_cfg(self) -> Dict:
        cfg = dict(self.config.get("discord") or {})
        token = os.getenv("DISCORD_TOKEN") or self.config.get("discord_token") or cfg.get("token")
        cfg["token"] = token
        if not cfg.get("default_channel_id"):
            channels = self.config.get("discord_channels") or cfg.get("channels") or []
            if channels:
                cfg["default_channel_id"] = str(channels[0])
        return cfg

    async def start_discord(self) -> bool:
        cfg = self._discord_cfg()
        if not cfg.get("enabled", True):
            live_log("⚠️ Discord отключён в config (discord.enabled=false)")
            return False
        if not cfg.get("token"):
            live_log("❌ Нет discord_token — укажите в config.json или DISCORD_TOKEN")
            return False
        try:
            self.discord = DiscordAPI(cfg["token"])
            # Колбэк на DM-ответы → CSV
            self.discord.set_reply_callback(self._on_discord_reply)
            await self.discord.connect()
            return True
        except Exception as e:
            live_log(f"❌ Не удалось подключиться к Discord: {e}")
            self.discord = None
            return False

    async def _on_discord_reply(
        self, user_id: str, username: str, classification: str, text: str
    ) -> None:
        """Ловим ответ в DM и пишем reply=yes/no/maybe в store + CSV."""
        self.contacted.record_reply(user_id, classification, text)
        self.update_csv_reply(user_id, classification, text)
        live_log(
            f"💬 Ответ от {username} ({user_id}): {classification} | {text[:120]}"
        )

    async def _seed_posts_for_test(self, touch: Dict) -> List[Dict]:
        """
        Если в канале нет человеческих постов (типично для пустого тестового сервера),
        берём test_user_id из конфига или owner_id гильдии — чтобы проверить реальный DM.
        """
        cfg = self._discord_cfg()
        if not cfg.get("allow_seed_dm", True):
            return []
        if not self.discord:
            return []

        channel_id = resolve_discord_channel_id(touch, cfg) or cfg.get("default_channel_id") or ""
        user_id = str(cfg.get("test_user_id") or "").strip()
        username = str(cfg.get("test_username") or "test_user")

        if not user_id and cfg.get("guild_id"):
            try:
                guild = await self.discord.get_guild(cfg["guild_id"])
                user_id = str(guild.get("owner_id") or "")
                username = "guild_owner"
                live_log(f"ℹ️ test_user_id не задан — берём owner гильдии: {user_id}")
            except Exception as e:
                live_log(f"⚠️ Не удалось получить owner гильдии: {e}")
                return []

        if not user_id:
            live_log(
                "⚠️ Нет кандидатов для DM. Напишите любое сообщение в #основной "
                "про localization/Steam ИЛИ укажите discord.test_user_id в config.json "
                "(ваш Discord User ID)."
            )
            return []

        if self.contacted.was_contacted_recently(user_id):
            live_log(f"⏭️ Seed-пользователь {user_id} уже в антиспам-листе")
            return []

        return [
            make_seed_post(
                user_id,
                username,
                str(channel_id),
                game_name=str(cfg.get("test_game_name") or "Ashen Hollow"),
            )
        ]

    async def find_recent_posts(self, channel_type: str, context: str, touch: Dict) -> List[Dict]:
        channel = channel_type.lower()

        if channel == "discord":
            if not self.discord:
                return []
            cfg = self._discord_cfg()
            channel_id = resolve_discord_channel_id(touch, cfg)
            if not channel_id:
                live_log("⚠️ Не задан discord.default_channel_id / channel_map")
                return []
            skip_ids = self.contacted.recently_contacted_ids()
            try:
                posts = await find_discord_posts(
                    self.discord,
                    channel_id,
                    keywords=cfg.get("keywords"),
                    fallback_latest=bool(cfg.get("fallback_latest", False)),
                    skip_user_ids=skip_ids,
                    limit=int(cfg.get("history_limit", 50)),
                )
                live_log(
                    f"🔍 Канал {channel_id}: найдено {len(posts)} релевантных постов "
                    f"(skip={len(skip_ids)})"
                )
                return posts
            except Exception as e:
                live_log(f"⚠️ Ошибка чтения Discord #{channel_id}: {e}")
                return []

        if channel == "reddit":
            subreddit = context.split("/")[-1].strip() if "/" in context else context
            return [
                {
                    "author": "indie_dev",
                    "title": "Need help with localization for my game",
                    "game_name": "Indie Adventure",
                    "url": f"https://reddit.com/r/{subreddit}/...",
                }
            ]

        if channel in ("tg", "telegram"):
            return [
                {
                    "author": "@indie_dev",
                    "content": "Кто-нибудь занимался локализацией игр?",
                    "game_name": "Моя игра",
                    "url": "https://t.me/indiedev/...",
                }
            ]

        if channel == "vk":
            return [
                {
                    "author": "id12345",
                    "content": "Разрабатываем игру, нужно перевести.",
                    "game_name": "Новая игра",
                    "url": "https://vk.com/wall-1_1",
                }
            ]

        return []

    async def generate_message(self, touch: Dict, post: Dict) -> str:
        game_name = post.get("game_name") or "your game"
        # Если имя не извлеклось — просим LLM вытащить из контента
        if game_name in ("your game", "вашу игру") and post.get("content"):
            game_name = await self._infer_game_name(post["content"], touch) or game_name
            post["game_name"] = game_name

        message = fill_template(touch["template_text"], game_name)
        prompt = build_personalize_prompt(message, game_name, touch)
        # Добавляем кусок реального поста для лучшей персонализации
        snippet = (post.get("content") or "")[:240]
        if snippet:
            prompt += f"\n\nФрагмент поста разработчика:\n{snippet}\n"

        try:
            personalized = await ask_ollama(prompt, self.config.get("llm"))
            if not personalized:
                return message
            if "gameforge.website" not in personalized:
                personalized += f"\n\nПодробнее: {touch['url']}"
            return personalized
        except Exception as e:
            live_log(f"⚠️ Ошибка генерации через LLM: {e}")
            return message

    async def _infer_game_name(self, content: str, touch: Dict) -> Optional[str]:
        lang = "English" if touch.get("language") == "EN" else "Russian"
        prompt = (
            f"Extract the game title from this gamedev post. "
            f"Reply with ONLY the title, or NONE.\nLanguage hint: {lang}\n\nPost:\n{content[:400]}"
        )
        try:
            raw = await ask_ollama(prompt, self.config.get("llm"), timeout=60)
            name = (raw or "").strip().strip('"').strip("'")
            if not name or name.upper() == "NONE" or len(name) > 60:
                return None
            return name
        except Exception:
            return None

    async def send_discord(self, touch: Dict, message: str, post: Dict) -> bool:
        """Пилот: приоритет — DM автору. Channel fallback только если явно включён."""
        cfg = self._discord_cfg()
        dry_run = bool(cfg.get("dry_run", False))
        prefer_dm = bool(cfg.get("prefer_dm", True))
        channel_fallback = bool(cfg.get("channel_fallback", False))
        template = (touch.get("template") or "").lower()
        channel_id = post.get("channel_id") or resolve_discord_channel_id(touch, cfg)
        author_id = post.get("author_id") or ""

        live_log(f"[Discord] {touch['template']} → {touch['context']} / @{post.get('author')}")
        live_log(f"Игра: {post.get('game_name')} | Сообщение: {message[:140]}...")

        if author_id and self.contacted.was_contacted_recently(author_id):
            live_log(f"⏭️ Антиспам: {author_id} уже контактирован за {self.contacted.cooldown_days}д")
            return False

        if dry_run:
            live_log("🟡 dry_run=true — реально не отправляем")
            if author_id:
                self.contacted.mark_contacted(
                    author_id,
                    username=post.get("author", ""),
                    touch_id=touch.get("id", ""),
                    game_name=post.get("game_name", ""),
                    message_id="dry_run",
                    channel_id=channel_id or "",
                )
            return True

        if not self.discord:
            live_log("❌ Discord клиент не запущен")
            return False

        # 1) DM (основной путь для пилота)
        want_dm = prefer_dm or template.startswith("dm")
        if want_dm:
            if not author_id:
                live_log("❌ Нет author_id для DM — пропускаем касание")
                return False
            try:
                result = await self.discord.send_dm(author_id, message)
                live_log(
                    f"✅ DM → {post.get('author')} ({author_id}) msg={result.get('id')}"
                )
                self.contacted.mark_contacted(
                    author_id,
                    username=post.get("author", ""),
                    touch_id=touch.get("id", ""),
                    game_name=post.get("game_name", ""),
                    message_id=result.get("id", ""),
                    channel_id=result.get("channel_id", ""),
                )
                return True
            except Exception as e:
                live_log(f"❌ DM не удался ({author_id}): {e}")
                if not channel_fallback:
                    # Не падаем — просто идём к следующему касанию
                    return False

        # 2) Опциональный fallback: reply/comment в канале
        if template.startswith("comment") or channel_fallback:
            if not channel_id:
                live_log("❌ Нет channel_id для channel-send")
                return False
            try:
                reply_to = post.get("message_id") or None
                result = await self.discord.send_channel_message(
                    channel_id, message, reply_to=reply_to
                )
                live_log(f"✅ Channel send → #{channel_id} msg={result.get('id')}")
                if author_id:
                    self.contacted.mark_contacted(
                        author_id,
                        username=post.get("author", ""),
                        touch_id=touch.get("id", ""),
                        game_name=post.get("game_name", ""),
                        message_id=result.get("id", ""),
                        channel_id=channel_id,
                    )
                return True
            except Exception as e:
                live_log(f"❌ Channel send failed: {e}")
                return False

        return False

    async def send_to_channel(self, touch: Dict, message: str, post: Dict) -> bool:
        channel_type = touch["channel"].lower()

        try:
            if channel_type == "discord":
                return await self.send_discord(touch, message, post)

            if channel_type == "reddit":
                live_log(f"[Reddit] stub — не настроено ({post.get('author')})")
                return False

            if channel_type in ("tg", "telegram"):
                live_log("[Telegram] stub — не настроено")
                return False

            if channel_type == "vk":
                live_log("[VK] stub — не настроено")
                return False

            return False
        except Exception as e:
            live_log(f"Ошибка отправки (продолжаем): {e}")
            return False

    async def run_day(
        self,
        discord_only: bool = True,
        limit: Optional[int] = None,
        listen_seconds: int = 0,
    ):
        cfg = self._discord_cfg()
        # Тест-драйв: limit из CLI или config.test_drive_limit
        if limit is None:
            if cfg.get("test_drive"):
                limit = int(cfg.get("test_drive_limit", 2))
            else:
                limit = int(cfg.get("daily_limit", 10))

        live_log(f"🚀 Запуск outreach на {datetime.now().strftime('%Y-%m-%d')}")
        live_log(f"📋 Касаний в плане: {len(self.touches)} | лимит запуска: {limit}")
        if limit <= 2:
            live_log("🧪 Режим тест-драйв (1–2 касания)")
        if discord_only:
            live_log("📌 Режим: только Discord (реальные посты + DM)")

        if not self.touches:
            live_log("❌ Не удалось распарсить касания из плана.")
            return

        ok = await self.start_discord()
        if not ok:
            live_log("❌ Без Discord продолжать нельзя в этом режиме.")
            return

        sent_count = 0
        results = []
        daily_touches = [t for t in self.touches if (not discord_only or t["channel"].lower() == "discord")]
        daily_touches = daily_touches[:limit]

        if cfg.get("dry_run"):
            live_log("🟡 discord.dry_run=true — сообщения только логируются")

        try:
            for touch in daily_touches:
                live_log(
                    f"--- Касание id={touch['id']}: {touch['channel']} {touch['template']} ---"
                )
                try:
                    posts = await self.find_recent_posts(
                        touch["channel"], touch["context"], touch
                    )

                    # Тест-драйв: если в канале нет людей — DM на test_user_id / owner сервера
                    if not posts and touch["channel"].lower() == "discord":
                        posts = await self._seed_posts_for_test(touch)
                        if posts:
                            live_log(
                                "🧪 Нет живых постов в канале — используем seed/test_user для проверки DM"
                            )

                    if not posts:
                        live_log(f"⚠️ Нет релевантных постов для {touch['context']}")
                        results.append(
                            {
                                "id": touch["id"],
                                "status": "no_posts_found",
                                "reason": "Не найдено свежих постов",
                            }
                        )
                        continue

                    # Берём первого ещё не контактированного
                    post = None
                    for candidate in posts:
                        aid = candidate.get("author_id") or ""
                        if aid and self.contacted.was_contacted_recently(aid):
                            continue
                        post = candidate
                        break
                    if post is None:
                        live_log("⏭️ Все кандидаты уже в антиспам-листе")
                        results.append(
                            {
                                "id": touch["id"],
                                "status": "skipped_contacted",
                                "reason": "Все авторы уже контактированы",
                            }
                        )
                        continue

                    live_log(
                        f"📥 Пост: @{post.get('author')} / «{post.get('game_name')}» "
                        f"(msg={post.get('message_id', 'n/a')})"
                    )
                    live_log(f"   Контент: {(post.get('content') or '')[:160]}")

                    message = await self.generate_message(touch, post)
                    success = await self.send_to_channel(touch, message, post)

                    if success:
                        sent_count += 1
                        results.append(
                            {
                                "id": touch["id"],
                                "status": "sent",
                                "post": {
                                    k: post.get(k)
                                    for k in (
                                        "author",
                                        "author_id",
                                        "game_name",
                                        "message_id",
                                        "channel_id",
                                        "url",
                                        "content",
                                    )
                                },
                                "message": message,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                        live_log(f"✅ Успех #{sent_count}/{len(daily_touches)}")
                    else:
                        results.append(
                            {
                                "id": touch["id"],
                                "status": "failed",
                                "reason": "DM/send не удался",
                                "post": {
                                    "author": post.get("author"),
                                    "author_id": post.get("author_id"),
                                },
                            }
                        )
                        live_log("➡️ Переходим к следующему касанию")

                except Exception as e:
                    live_log(f"❌ Ошибка на касании {touch['id']} (не роняем цикл): {e}")
                    results.append(
                        {"id": touch["id"], "status": "failed", "reason": str(e)[:200]}
                    )

                if sent_count < len(daily_touches):
                    delay = random.randint(
                        int(cfg.get("delay_min", 20)), int(cfg.get("delay_max", 60))
                    )
                    live_log(f"⏳ Пауза {delay} сек…")
                    await asyncio.sleep(delay)

            # После отправок можно послушать ответы
            listen_for = listen_seconds or int(cfg.get("listen_replies_seconds", 0))
            if listen_for > 0 and self.discord:
                await self.discord.listen_replies(listen_for)

        finally:
            if self.discord:
                await self.discord.close()

        self.save_results(results)
        self.update_csv_status(results)
        self.print_conversion_summary(results)

    def print_conversion_summary(self, results: List[Dict]) -> None:
        sent = len([r for r in results if r["status"] == "sent"])
        failed = len([r for r in results if r["status"] == "failed"])
        no_posts = len([r for r in results if r["status"] == "no_posts_found"])
        skipped = len([r for r in results if r["status"] == "skipped_contacted"])
        replies = [
            u for u in self.contacted.recent_contacts() if u.get("reply")
        ]
        yes = len([r for r in replies if r.get("reply") == "yes"])
        maybe = len([r for r in replies if r.get("reply") == "maybe"])
        no = len([r for r in replies if r.get("reply") == "no"])

        live_log("=" * 50)
        live_log("📊 ИТОГИ / КОНВЕРСИЯ")
        live_log(f"Отправлено: {sent}")
        live_log(f"Нет постов: {no_posts} | Скип антиспам: {skipped} | Ошибки: {failed}")
        live_log(f"Ответы (накопленно): yes={yes} maybe={maybe} no={no}")
        live_log("=" * 50)

    def save_results(self, results: List[Dict]):
        log_file = LOGS_DIR / f"outreach_log_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": datetime.now().isoformat(),
                    "results": results,
                    "contacted_snapshot": self.contacted.recent_contacts()[:50],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        live_log(f"📝 Лог сохранен в {log_file}")

    def _ensure_csv(self, csv_file: Path) -> tuple[List[str], List[List[str]]]:
        if not csv_file.exists():
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
            return list(CSV_HEADERS), []

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, list(CSV_HEADERS))
            rows = list(reader)

        # Миграция старых заголовков → расширенная схема
        if "author_id" not in headers or "reply" not in headers:
            old_rows = rows
            new_rows = []
            for row in old_rows:
                mapped = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
                new_rows.append(
                    [
                        mapped.get("id", ""),
                        mapped.get("status", ""),
                        mapped.get("sent_at", ""),
                        mapped.get("author", ""),
                        mapped.get("author_id", ""),
                        mapped.get("game_name", ""),
                        mapped.get("reply", ""),
                        mapped.get("reply_at", ""),
                        mapped.get("notes", ""),
                    ]
                )
            headers = list(CSV_HEADERS)
            rows = new_rows
        return headers, rows

    def update_csv_status(self, results: List[Dict]):
        csv_file = LEADS_CSV
        headers, rows = self._ensure_csv(csv_file)

        known_ids = {row[0] for row in rows if row}
        for result in results:
            rid = result["id"]
            if rid not in known_ids:
                rows.append([rid, "pending", "", "", "", "", "", "", ""])
                known_ids.add(rid)

        for result in results:
            post = result.get("post") or {}
            for row in rows:
                if not row or row[0] != result["id"]:
                    continue
                while len(row) < len(CSV_HEADERS):
                    row.append("")
                if result["status"] == "sent":
                    row[1] = "sent"
                    row[2] = datetime.now().strftime("%Y-%m-%d")
                    row[3] = post.get("author", row[3])
                    row[4] = post.get("author_id", row[4])
                    row[5] = post.get("game_name", row[5])
                elif result["status"] == "no_posts_found":
                    row[1] = "pending_no_post"
                elif result["status"] == "failed":
                    row[1] = "failed"
                    row[8] = (result.get("reason") or "")[:120]
                elif result["status"] == "skipped_contacted":
                    row[1] = "skipped_contacted"

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers if headers == CSV_HEADERS else CSV_HEADERS)
            writer.writerows(rows)
        live_log(f"✅ CSV обновлен: {csv_file}")

    def update_csv_reply(self, author_id: str, reply: str, reply_text: str = "") -> None:
        """Обновляет поле reply у строки с данным author_id."""
        csv_file = LEADS_CSV
        headers, rows = self._ensure_csv(csv_file)        changed = False
        for row in rows:
            while len(row) < len(CSV_HEADERS):
                row.append("")
            if row[4] == str(author_id):
                row[6] = reply
                row[7] = datetime.now().strftime("%Y-%m-%d %H:%M")
                if reply_text:
                    row[8] = reply_text[:120]
                changed = True
        if changed:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                writer.writerows(rows)


async def watch_replies_only(seconds: int = 1800) -> None:
    """Отдельный режим: только слушать DM-ответы."""
    automation = OutreachDayAutomation()
    ok = await automation.start_discord()
    if not ok:
        return
    try:
        await automation.discord.listen_replies(seconds)
    finally:
        await automation.discord.close()


async def main():
    parser = argparse.ArgumentParser(description="LocForge Discord outreach agent")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Тест-драйв: сколько касаний выполнить (например 1 или 2)",
    )
    parser.add_argument(
        "--listen",
        type=int,
        default=0,
        help="После отправки слушать DM-ответы N секунд",
    )
    parser.add_argument(
        "--watch-replies",
        type=int,
        default=0,
        help="Только слушать DM-ответы N секунд (без отправки)",
    )
    parser.add_argument(
        "--all-channels",
        action="store_true",
        help="Не фильтровать только Discord (по умолчанию Discord-only)",
    )
    parser.add_argument(
        "--plan",
        default=str(DEFAULT_PLAN.name),
        help="Markdown day-план из plans/ (например day-discord-accessible.md)",
    )
    args = parser.parse_args()

    ensure_dirs()
    config = Config(str(CONFIG_PATH))
    if not config.get("llm"):
        config.set(
            "llm",
            {
                "provider": "ollama",
                "model": "qwen2.5:7b-instruct-q4_K_M",
                "api_base": "http://127.0.0.1:11434",
            },
        )

    if args.watch_replies:
        await watch_replies_only(args.watch_replies)
        return

    automation = OutreachDayAutomation(args.plan)
    await automation.run_day(
        discord_only=not args.all_channels,
        limit=args.limit,
        listen_seconds=args.listen,
    )


if __name__ == "__main__":
    asyncio.run(main())
