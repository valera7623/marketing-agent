#!/usr/bin/env python3
"""Scout Indie Park #vos-créations for Day 3 — print lead signals only."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "data" / "config.json").read_text(encoding="utf-8"))
token = cfg["discord_token"]
cid = "1064526595030782043"
skip = {
    "zebra3d",
    "Mephistase",
    "color500",
    "Olonnais",
    "Razjinh",
    "papapoule75",
    "valera7623",
}
keys = (
    "steam",
    "local",
    "traduc",
    "transl",
    "csv",
    "wishlist",
    "feedback",
    "demo",
    "alpha",
    "playtest",
    "showcase",
    "release",
    "avis",
    "retour",
    "multilang",
    "langue",
    "itch",
    "test",
)

req = urllib.request.Request(
    f"https://discord.com/api/v10/channels/{cid}/messages?limit=50",
    headers={"Authorization": f"Bot {token}", "User-Agent": "LocForgeScout/1.0"},
)
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        msgs = json.loads(r.read().decode())
except Exception as e:
    print("ERR", type(e).__name__, e)
    raise SystemExit(1)

print("OK", len(msgs))
for m in msgs:
    a = m.get("author") or {}
    un = a.get("username") or ""
    if un in skip or a.get("bot"):
        continue
    content = (m.get("content") or "").replace("\n", " ")
    low = content.lower()
    signals = any(k in low for k in keys) or "store.steampowered" in low
    if signals or len(content) > 80:
        mid = m["id"]
        url = f"https://discord.com/channels/1021378341267320872/{cid}/{mid}"
        print("---")
        print("id", mid)
        print("user", un)
        print("sig", int(signals))
        print("url", url)
        print("text", content[:280])
