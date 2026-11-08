"""Bus de eventos en memoria para enviar avisos en tiempo real (Server-Sent Events)."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[channel].add(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        self._subs[channel].discard(q)

    def publish(self, channel: str, event: str, data: dict) -> None:
        payload = {"evento": event, "datos": data}
        for q in list(self._subs[channel]):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def publish_many(self, channels: list[str], event: str, data: dict) -> None:
        for ch in channels:
            self.publish(ch, event, data)


def sse_format(payload: dict) -> str:
    return f"event: {payload['evento']}\ndata: {json.dumps(payload['datos'], ensure_ascii=False)}\n\n"


bus = EventBus()
