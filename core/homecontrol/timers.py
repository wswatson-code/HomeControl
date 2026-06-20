"""Countdown timers / alarms, owned by the Core Service.

These live in the core (not the voice service) on purpose: a timer must survive a voice
restart, show on the kiosk even when set by touch, and fire regardless of what created it.
Each timer schedules an asyncio task that, on elapse, flips it to FIRED and republishes the
list — the kiosk plays the alarm sound and offers a dismiss. A fired timer stays in the
list (ringing) until explicitly dismissed.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from .models import TimerInfo, TimerState

PublishTimers = Callable[[list[TimerInfo]], Awaitable[None]]


def _now_ms() -> int:
    return int(time.time() * 1000)


class TimerManager:
    def __init__(self, publish: PublishTimers) -> None:
        self._publish = publish
        self._timers: dict[str, TimerInfo] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._seq = 0

    def list(self) -> list[TimerInfo]:
        return list(self._timers.values())

    async def create(self, duration_ms: int, label: str = "") -> TimerInfo:
        self._seq += 1
        timer_id = f"t{self._seq}"
        timer = TimerInfo(
            id=timer_id,
            label=label,
            duration_ms=duration_ms,
            fires_at_ms=_now_ms() + duration_ms,
            state=TimerState.RUNNING,
        )
        self._timers[timer_id] = timer
        self._tasks[timer_id] = asyncio.create_task(self._run(timer_id, duration_ms))
        await self._publish(self.list())
        return timer

    async def dismiss(self, timer_id: str) -> bool:
        """Cancel (if running) or clear (if ringing). Returns False if no such timer."""
        existed = timer_id in self._timers
        self._cancel_task(timer_id)
        self._timers.pop(timer_id, None)
        if existed:
            await self._publish(self.list())
        return existed

    async def _run(self, timer_id: str, duration_ms: int) -> None:
        try:
            await asyncio.sleep(duration_ms / 1000)
        except asyncio.CancelledError:
            return
        timer = self._timers.get(timer_id)
        if timer is None:  # dismissed while we slept
            return
        timer.state = TimerState.FIRED
        self._tasks.pop(timer_id, None)
        await self._publish(self.list())

    def _cancel_task(self, timer_id: str) -> None:
        task = self._tasks.pop(timer_id, None)
        if task is not None:
            task.cancel()

    async def stop(self) -> None:
        for timer_id in list(self._tasks):
            self._cancel_task(timer_id)
        self._timers.clear()
