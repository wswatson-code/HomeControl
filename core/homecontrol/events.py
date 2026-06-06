"""A tiny async pub/sub bus.

The Core Service is event-driven: subsystems (Spotify, voice, intercom, mesh) mutate
state and publish events; the WebSocket layer and the inter-unit mesh subscribe. One
process, many asyncio consumers — so an in-memory fan-out queue per subscriber is all
we need. No external broker.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from .models import Event


class EventBus:
    def __init__(self, *, max_queue: int = 256) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._max_queue = max_queue

    async def publish(self, event: Event) -> None:
        # Fan out to every subscriber. A slow consumer drops events rather than
        # blocking the publisher — UI clients re-sync from the next snapshot.
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
