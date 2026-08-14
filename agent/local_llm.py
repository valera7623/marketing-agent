"""Минимальный клиент локальной модели через Ollama (без pynions/litellm)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import httpx


class Config:
    def __init__(self, path: str = "config.json"):
        self.path = Path(path)
        self._data: Dict[str, Any] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _normalize_api_base(api_base: str) -> str:
    """localhost у httpx на Windows часто зависает — форсим 127.0.0.1."""
    parsed = urlparse(api_base.rstrip("/"))
    host = parsed.hostname or "127.0.0.1"
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{host}{port}"
    return urlunparse((parsed.scheme or "http", netloc, parsed.path.rstrip("/"), "", "", ""))


async def ask_ollama(
    prompt: str,
    llm_config: Optional[Dict[str, Any]] = None,
    timeout: float = 180.0,
) -> str:
    """Генерация текста через Ollama /api/generate."""
    cfg = llm_config or {}
    api_base = _normalize_api_base(cfg.get("api_base") or "http://127.0.0.1:11434")
    model = cfg.get("model") or "qwen2.5:7b-instruct-q4_K_M"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 512,
        },
    }

    # trust_env=False — не уводить локальный Ollama в системный HTTP-прокси
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.post(f"{api_base}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()
