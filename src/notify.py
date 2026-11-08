"""ntfy.sh へのプッシュ通知（アカウント不要。トピック名は環境変数 NTFY_TOPIC）"""
from __future__ import annotations

import os

import requests

NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")


def send(note: dict, page_url: str = "", search_url: str = "") -> bool:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print(f"[notify:dry-run] {note['title']} | {note['body']}")
        return False
    # JSON方式で送る（ヘッダー方式は日本語タイトルが使えないため）
    payload = {"topic": topic, "title": note["title"], "message": note["body"],
               "priority": {"min": 1, "low": 2, "default": 3, "high": 4, "max": 5}[note["priority"]],
               "tags": [t for t in note.get("tags", "").split(",") if t]}
    if page_url:
        payload["click"] = page_url
    if search_url:
        payload["actions"] = [{"action": "view", "label": "Trip.comで開く", "url": search_url}]
    try:
        r = requests.post(NTFY_SERVER, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[notify] sent: {note['title']}")
        return True
    except Exception as e:  # 通知失敗で全体を止めない
        print(f"[notify] failed: {e}")
        return False
