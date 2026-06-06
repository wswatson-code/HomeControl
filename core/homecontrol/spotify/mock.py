"""A credential-free, hardware-free Spotify stand-in.

Simulates a small playlist that advances in real time so the UI and API can be built
and demoed on any machine. Swapped for the librespot-backed provider in Phase 2.
"""

from __future__ import annotations

import asyncio
import contextlib

from ..models import PlaybackState, PlayerState, RepeatMode, Track
from .base import PublishPlayer, SpotifyProvider

_PLAYLIST = [
    Track(id="t1", title="Midnight City", artist="M83", album="Hurry Up, We're Dreaming", duration_ms=244_000),
    Track(id="t2", title="Redbone", artist="Childish Gambino", album="Awaken, My Love!", duration_ms=327_000),
    Track(id="t3", title="Teardrop", artist="Massive Attack", album="Mezzanine", duration_ms=329_000),
]

_TICK_MS = 1000


class MockSpotify(SpotifyProvider):
    def __init__(self, publish: PublishPlayer) -> None:
        super().__init__(publish)
        self._index = 0
        self._state = PlayerState(
            state=PlaybackState.PAUSED,
            track=_PLAYLIST[0],
            position_ms=0,
            volume=50,
            repeat=RepeatMode.OFF,
        )
        self._task: asyncio.Task | None = None

    def snapshot(self) -> PlayerState:
        return self._state.model_copy(deep=True)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(_TICK_MS / 1000)
            if self._state.state is not PlaybackState.PLAYING or self._state.track is None:
                continue
            self._state.position_ms += _TICK_MS
            if self._state.position_ms >= self._state.track.duration_ms:
                await self._advance(+1, autoplay=True)
            await self._emit()

    # ---- transport ------------------------------------------------------------

    async def play(self) -> None:
        self._state.state = PlaybackState.PLAYING
        await self._emit()

    async def pause(self) -> None:
        self._state.state = PlaybackState.PAUSED
        await self._emit()

    async def next(self) -> None:
        await self._advance(+1, autoplay=self._state.state is PlaybackState.PLAYING)

    async def previous(self) -> None:
        # Restart the track if we're more than 3s in, otherwise go back one.
        if self._state.position_ms > 3000:
            self._state.position_ms = 0
        else:
            await self._advance(-1, autoplay=self._state.state is PlaybackState.PLAYING)
        await self._emit()

    async def seek(self, position_ms: int) -> None:
        if self._state.track:
            self._state.position_ms = min(position_ms, self._state.track.duration_ms)
        await self._emit()

    async def set_volume(self, volume: int) -> None:
        self._state.volume = max(0, min(100, volume))
        await self._emit()

    # ---- helpers --------------------------------------------------------------

    async def _advance(self, delta: int, *, autoplay: bool) -> None:
        self._index = (self._index + delta) % len(_PLAYLIST)
        self._state.track = _PLAYLIST[self._index]
        self._state.position_ms = 0
        self._state.state = PlaybackState.PLAYING if autoplay else PlaybackState.PAUSED

    async def _emit(self) -> None:
        await self._publish(self.snapshot())
