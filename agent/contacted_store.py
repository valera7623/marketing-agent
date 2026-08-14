"""Хранилище уже контактированных Discord-пользователей (антиспам)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class ContactedStore:
    """Запоминает user_id, которым уже писали (по умолчанию 7 дней)."""

    def __init__(self, path: str | Path = "contacted_users.json", cooldown_days: int = 7):
        self.path = Path(path)
        self.cooldown_days = cooldown_days
        self._data: Dict[str, Any] = {"users": {}}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {"users": {}}
        if "users" not in self._data:
            self._data["users"] = {}

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _parse_ts(self, value: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    def was_contacted_recently(self, user_id: str | int) -> bool:
        uid = str(user_id)
        entry = self._data["users"].get(uid)
        if not entry:
            return False
        sent_at = self._parse_ts(entry.get("sent_at", ""))
        if not sent_at:
            return False
        return datetime.now() - sent_at < timedelta(days=self.cooldown_days)

    def mark_contacted(
        self,
        user_id: str | int,
        *,
        username: str = "",
        touch_id: str = "",
        game_name: str = "",
        message_id: str = "",
        channel_id: str = "",
    ) -> None:
        uid = str(user_id)
        prev = self._data["users"].get(uid) or {}
        self._data["users"][uid] = {
            "username": username,
            "touch_id": touch_id,
            "game_name": game_name,
            "message_id": str(message_id),
            "channel_id": str(channel_id),
            "sent_at": datetime.now().isoformat(),
            "reply": prev.get("reply", ""),
            "reply_at": prev.get("reply_at", ""),
            "reply_text": prev.get("reply_text", ""),
        }
        self.save()

    def record_reply(self, user_id: str | int, reply: str, reply_text: str = "") -> None:
        uid = str(user_id)
        entry = self._data["users"].setdefault(uid, {"sent_at": datetime.now().isoformat()})
        entry["reply"] = reply
        entry["reply_at"] = datetime.now().isoformat()
        entry["reply_text"] = reply_text[:500]
        self.save()

    def recently_contacted_ids(self) -> set[str]:
        return {
            uid
            for uid in self._data.get("users", {})
            if self.was_contacted_recently(uid)
        }

    def find_by_user(self, user_id: str | int) -> Optional[Dict[str, Any]]:
        return self._data["users"].get(str(user_id))

    def recent_contacts(self) -> List[Dict[str, Any]]:
        rows = []
        for uid, entry in self._data["users"].items():
            rows.append({"user_id": uid, **entry})
        rows.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
        return rows
