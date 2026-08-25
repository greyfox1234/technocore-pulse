"""Real-time room monitoring and webhook notification engine."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable
from technocore_pulse.client import TechnocoreClient


class PulseMonitor:
    """Monitors rooms and triggers alerts when filters match."""

    def __init__(
        self,
        client: TechnocoreClient,
        rooms: list[str],
        keywords: list[str] | None = None,
        sender_dids: list[str] | None = None,
        webhook_url: str | None = None,
        on_message: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.client = client
        self.rooms = rooms
        self.keywords = [k.lower() for k in (keywords or [])]
        self.sender_dids = set(sender_dids or [])
        self.webhook_url = webhook_url
        self.on_message = on_message

    def matches(self, msg: dict[str, Any]) -> bool:
        """Check if message matches configured criteria."""
        text = msg.get("text", "").lower()
        sender = msg.get("from", "")

        if self.keywords:
            if not any(kw in text for kw in self.keywords):
                return False

        if self.sender_dids:
            if sender not in self.sender_dids:
                return False

        return True

    def dispatch_webhook(self, room: str, msg: dict[str, Any]) -> None:
        """Send formatted alert payload to configured webhook."""
        if not self.webhook_url:
            return

        payload = {
            "content": f"[Technocore Notification] Room #{room} | Seq {msg.get('seq')} | From: {msg.get('from')}\nMessage: {msg.get('text')}",
            "room": room,
            "message": msg,
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "TechnocorePulse/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0):
                pass
        except Exception as e:
            print(f"[Warning] Webhook dispatch failed: {e}")

    def run_once(self) -> list[dict[str, Any]]:
        """Fetch latest messages across rooms and process matching items."""
        found = []
        for room in self.rooms:
            data = self.client.read_room(room, limit=20)
            for msg in data.get("messages", []):
                if self.matches(msg):
                    found.append({"room": room, "msg": msg})
                    if self.on_message:
                        self.on_message(room, msg)
                    if self.webhook_url:
                        self.dispatch_webhook(room, msg)
        return found
