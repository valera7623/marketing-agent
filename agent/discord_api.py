"""Discord REST-клиент (стабильнее gateway discord.py на Windows).

Поиск постов, DM и опрос ответов — через HTTPS API.
discord.py оставлен опционально только если gateway доступен.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import requests

DISCORD_API = "https://discord.com/api/v10"

DEFAULT_KEYWORDS = [
    "localiz",
    "localisation",
    "localization",
    "translate",
    "translation",
    "перевод",
    "локализ",
    "мультиязыч",
    "multilang",
    "multi-lang",
    "i18n",
    "l10n",
    "csv",
    "steam",
    "wishlist",
    "godot",
    "unity",
    "unreal",
    "indie",
    "released",
    "release",
    "showcase",
    "языки",
    "language",
]

# callback(user_id, username, classification, text)
ReplyCallback = Callable[[str, str, str, str], Awaitable[None]]


class DiscordAPI:
    """REST-обёртка: connect / history / send_dm / poll replies."""

    def __init__(self, token: str, timeout: float = 30.0):
        if not token:
            raise ValueError("discord_token пуст")
        self.token = token.strip()
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bot {self.token}",
            "User-Agent": "LocForgeOutreachBot (gameforge.website, 1.0)",
            "Content-Type": "application/json",
        }
        self.bot_user: Optional[Dict[str, Any]] = None
        self._reply_callback: Optional[ReplyCallback] = None
        self._seen_reply_ids: set[str] = set()

    async def connect(self) -> None:
        me = await self._request("GET", "/users/@me")
        self.bot_user = {
            "id": str(me.get("id", "")),
            "username": me.get("username", ""),
            "bot": bool(me.get("bot")),
        }
        print(f"🤖 Discord REST: вошли как {self.bot_user['username']} (bot={self.bot_user['bot']})")

    async def close(self) -> None:
        return None

    def set_reply_callback(self, callback: Optional[ReplyCallback]) -> None:
        self._reply_callback = callback

    def _request_sync(self, method: str, path: str, **kwargs) -> Any:
        url = f"{DISCORD_API}{path}"
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                    **kwargs,
                )
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "2"))
                    time.sleep(min(retry_after, 15))
                    continue
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Discord API {response.status_code} {method} {path}: {response.text[:400]}"
                    )
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                time.sleep(1.5 * attempt)
        raise RuntimeError(f"Discord API недоступен после повторов: {last_error}")

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        return await asyncio.to_thread(self._request_sync, method, path, **kwargs)

    async def get_channel_messages(self, channel_id: int | str, limit: int = 50) -> List[Dict]:
        return await self._request(
            "GET",
            f"/channels/{channel_id}/messages",
            params={"limit": min(int(limit), 100)},
        )

    async def get_guild(self, guild_id: int | str) -> Dict:
        return await self._request("GET", f"/guilds/{guild_id}")

    async def send_channel_message(
        self,
        channel_id: int | str,
        content: str,
        reply_to: Optional[str] = None,
    ) -> Dict:
        payload: Dict[str, Any] = {"content": content[:2000]}
        if reply_to:
            payload["message_reference"] = {"message_id": str(reply_to)}
            payload["allowed_mentions"] = {"replied_user": True}
        return await self._request("POST", f"/channels/{channel_id}/messages", json=payload)

    async def send_dm(self, user_id: int | str, content: str) -> Dict:
        dm = await self._request(
            "POST",
            "/users/@me/channels",
            json={"recipient_id": str(user_id)},
        )
        channel_id = dm["id"]
        sent = await self._request(
            "POST",
            f"/channels/{channel_id}/messages",
            json={"content": content[:2000]},
        )
        return {
            "id": str(sent.get("id", "")),
            "channel_id": str(channel_id),
            "user_id": str(user_id),
        }

    async def list_dm_channels(self) -> List[Dict]:
        # Private channels visible to the bot
        return await self._request("GET", "/users/@me/channels")

    async def poll_dm_replies_once(self) -> int:
        """Один проход по DM-каналам: новые сообщения от людей → callback."""
        if not self._reply_callback:
            return 0
        bot_id = str((self.bot_user or {}).get("id", ""))
        found = 0
        try:
            channels = await self.list_dm_channels()
        except Exception:
            return 0

        for ch in channels:
            if ch.get("type") != 1:  # DM
                continue
            cid = ch.get("id")
            try:
                messages = await self.get_channel_messages(cid, limit=10)
            except Exception:
                continue
            for msg in messages:
                mid = str(msg.get("id", ""))
                if not mid or mid in self._seen_reply_ids:
                    continue
                author = msg.get("author") or {}
                if author.get("bot") or str(author.get("id", "")) == bot_id:
                    self._seen_reply_ids.add(mid)
                    continue
                content = (msg.get("content") or "").strip()
                if not content:
                    self._seen_reply_ids.add(mid)
                    continue
                self._seen_reply_ids.add(mid)
                classification = classify_reply(content)
                await self._reply_callback(
                    str(author.get("id", "")),
                    author.get("username") or "user",
                    classification,
                    content,
                )
                found += 1
        return found

    async def _mark_existing_dm_messages_seen(self) -> None:
        bot_id = str((self.bot_user or {}).get("id", ""))
        try:
            channels = await self.list_dm_channels()
        except Exception:
            return
        for ch in channels:
            if ch.get("type") != 1:
                continue
            try:
                messages = await self.get_channel_messages(ch.get("id"), limit=10)
            except Exception:
                continue
            for msg in messages:
                mid = str(msg.get("id", ""))
                if mid:
                    self._seen_reply_ids.add(mid)

    async def listen_replies(self, seconds: int = 600, interval: int = 15) -> None:
        """Поллинг DM вместо gateway — работает там, где discord.py зависает."""
        print(f"👂 Слушаем DM-ответы {seconds} сек (poll каждые {interval}с)…")
        await self._mark_existing_dm_messages_seen()
        deadline = time.time() + seconds
        while time.time() < deadline:
            n = await self.poll_dm_replies_once()
            if n:
                print(f"   +{n} новых ответов")
            await asyncio.sleep(interval)


def resolve_discord_channel_id(touch: Dict, discord_cfg: Dict) -> Optional[str]:
    channel_map = discord_cfg.get("channel_map") or {}
    context = (touch.get("context") or "").lower()

    for key, channel_id in channel_map.items():
        if str(key).lower() in context:
            return str(channel_id)

    default_id = discord_cfg.get("default_channel_id")
    if default_id:
        return str(default_id)

    channels = discord_cfg.get("channels") or []
    if channels:
        return str(channels[0])
    return None


def extract_game_name(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return "your game"

    patterns = [
        r'["«“]([^"»”]{2,60})["»”]',
        r"\b(?:game|project|title)\s+(?:called|named|is|:)\s*[\"«]?([A-Za-z0-9][\w\s\-:'!]{1,50})",
        r"\bmy\s+(?:game|project)\s+[\"«]?([A-Za-z0-9][\w\s\-:'!]{1,50})",
        r"(?:игра|проект|тайтл)\s*(?:называется|под названием|:)?\s*[«\"]?([А-Яа-яA-Za-z0-9][\w\s\-:'!]{1,50})",
        r"\b(?:working on|building|shipping|released)\s+[\"«]?([A-Za-z][\w\s\-:'!]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .,!?:;—-")
            if name.lower() in {"game", "project", "steam", "godot", "unity", "help", "игра", "проект"}:
                continue
            if 2 <= len(name) <= 60:
                return name
    return "your game"


def message_to_post(msg: Dict, channel_id: str) -> Dict:
    author = msg.get("author") or {}
    content = msg.get("content") or ""
    guild_hint = msg.get("guild_id") or "@me"
    return {
        "author": author.get("username") or author.get("global_name") or "unknown",
        "author_id": str(author.get("id", "")),
        "content": content,
        "game_name": extract_game_name(content),
        "message_id": str(msg.get("id", "")),
        "channel_id": str(channel_id),
        "url": f"https://discord.com/channels/{guild_hint}/{channel_id}/{msg.get('id', '')}",
    }


async def find_discord_posts(
    api: DiscordAPI,
    channel_id: str,
    keywords: Optional[List[str]] = None,
    limit: int = 50,
    fallback_latest: bool = False,
    skip_user_ids: Optional[set[str]] = None,
) -> List[Dict]:
    keywords = [k.lower() for k in (keywords or DEFAULT_KEYWORDS)]
    skip_user_ids = skip_user_ids or set()
    bot_id = str((api.bot_user or {}).get("id", ""))
    messages = await api.get_channel_messages(channel_id, limit=limit)

    matched: List[Dict] = []
    latest_human: Optional[Dict] = None

    for msg in messages:
        author = msg.get("author") or {}
        author_id = str(author.get("id", ""))
        if author.get("bot"):
            continue
        if author_id == bot_id or author_id in skip_user_ids:
            continue

        content = (msg.get("content") or "").strip()
        if not content:
            continue

        post = message_to_post(msg, channel_id)
        if latest_human is None:
            latest_human = post

        lowered = content.lower()
        if any(k in lowered for k in keywords):
            matched.append(post)

    if matched:
        return matched
    if fallback_latest and latest_human:
        return [latest_human]
    return []


def classify_reply(text: str) -> str:
    t = (text or "").lower()
    yes_words = ["yes", "yeah", "yep", "sure", "ok", "okay", "interested", "да", "конечно", "интересно", "го", "давай"]
    no_words = ["no", "nope", "not interested", "stop", "unsubscribe", "нет", "не надо", "не интересно", "отстань"]
    maybe_words = ["maybe", "later", "perhaps", "возможно", "может", "потом", "подумаю", "не уверен"]

    if any(w in t for w in no_words):
        return "no"
    if any(w in t for w in yes_words):
        return "yes"
    if any(w in t for w in maybe_words):
        return "maybe"
    return "maybe"


def make_seed_post(user_id: str, username: str, channel_id: str, game_name: str = "Ashen Hollow") -> Dict:
    """Синтетический пост для тест-драйва DM, когда в канале нет людей."""
    return {
        "author": username or "test_user",
        "author_id": str(user_id),
        "content": (
            f'Just released my game "{game_name}" on Steam. '
            "Looking for localization help (RU/ES/DE), have key,source CSV."
        ),
        "game_name": game_name,
        "message_id": "",
        "channel_id": str(channel_id),
        "url": f"https://discord.com/channels/@me/{channel_id}",
        "seed": True,
    }
