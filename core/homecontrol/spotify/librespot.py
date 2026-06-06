"""librespot-backed Spotify provider.

librespot itself runs as a separate, systemd-supervised Connect receiver (see
provisioning/). This provider does NOT spawn it — it:

  * ingests librespot `--onevent` hooks (low-latency state: track changed, play/pause,
    volume) posted to /internal/spotify/event by the onevent script, and
  * drives transport and pulls metadata through the Spotify Web API (`SpotifyWebClient`),
    reconciling position drift by polling `GET /me/player` periodically.

So events give us *fast* state, the Web API gives us *rich* state and control.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from ..config import Settings
from ..models import PlaybackState, PlayerState, RepeatMode, Track
from .base import PublishPlayer, SpotifyProvider
from .web import SpotifyWebClient

_TICK_MS = 1000
_RECONCILE_S = 10


@dataclass
class PlayerEvent:
    """Normalized librespot event (the pure result of parsing the onevent env)."""

    kind: str  # started | changed | playing | paused | stopped | volume | preloading
    track_id: str | None = None
    duration_ms: int | None = None
    position_ms: int | None = None
    volume: int | None = None  # 0-100, already normalized


def parse_player_event(env: dict[str, str]) -> PlayerEvent | None:
    """Map librespot's --onevent environment into a PlayerEvent. Pure + testable."""
    kind = env.get("PLAYER_EVENT")
    if not kind:
        return None

    def _int(key: str) -> int | None:
        val = env.get(key)
        return int(val) if val is not None and val.isdigit() else None

    return PlayerEvent(
        kind=kind,
        track_id=env.get("TRACK_ID"),
        duration_ms=_int("DURATION_MS"),
        position_ms=_int("POSITION_MS"),
        volume=_normalize_volume(_int("VOLUME")),
    )


def _normalize_volume(raw: int | None) -> int | None:
    """librespot reports volume as a 16-bit value (0-65535); the API speaks 0-100.
    Values already in 0-100 are passed through (older/odd builds)."""
    if raw is None:
        return None
    if raw > 100:
        return round(raw / 65535 * 100)
    return max(0, min(100, raw))


class LibrespotSpotify(SpotifyProvider):
    def __init__(self, publish: PublishPlayer, settings: Settings) -> None:
        super().__init__(publish)
        self._settings = settings
        self._web = SpotifyWebClient(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            refresh_token=settings.spotify_refresh_token,
            device_name=settings.resolved_device_name(),
        )
        self._state = PlayerState(state=PlaybackState.STOPPED, volume=50, repeat=RepeatMode.OFF)
        self._current_track_id: str | None = None
        self._tasks: list[asyncio.Task] = []

    def snapshot(self) -> PlayerState:
        return self._state.model_copy(deep=True)

    async def start(self) -> None:
        with contextlib.suppress(Exception):
            await self._web.device_id(refresh=True)
            await self._reconcile()
        self._tasks = [
            asyncio.create_task(self._tick_loop()),
            asyncio.create_task(self._reconcile_loop()),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._web.aclose()

    # --- event ingest (fast path) ---------------------------------------------

    async def handle_event(self, env: dict[str, str]) -> None:
        event = parse_player_event(env)
        if event is None:
            return

        if event.kind in ("started", "changed", "playing"):
            self._state.state = PlaybackState.PLAYING
            if event.position_ms is not None:
                self._state.position_ms = event.position_ms
            if event.track_id and event.track_id != self._current_track_id:
                await self._load_track(event.track_id, event.duration_ms)
        elif event.kind == "paused":
            self._state.state = PlaybackState.PAUSED
            if event.position_ms is not None:
                self._state.position_ms = event.position_ms
        elif event.kind == "stopped":
            self._state.state = PlaybackState.STOPPED
        elif event.kind == "volume" and event.volume is not None:
            self._state.volume = event.volume

        await self._emit()

    async def _load_track(self, track_id: str, duration_ms: int | None) -> None:
        self._current_track_id = track_id
        self._state.position_ms = 0
        # A metadata fetch failure (network blip, token issue) must never break the
        # event path. Fall back to a bare track (id + duration from the event) so the
        # progress bar still works while we lack title/artist/art.
        try:
            track = await self._web.get_track(track_id)
        except Exception:
            track = None
        if track is None and duration_ms:
            track = Track(id=track_id, title="", artist="", duration_ms=duration_ms)
        self._state.track = track

    # --- control (delegated to the Web API) -----------------------------------

    async def play(self) -> None:
        await self._web.play()

    async def pause(self) -> None:
        await self._web.pause()

    async def next(self) -> None:
        await self._web.next()

    async def previous(self) -> None:
        await self._web.previous()

    async def seek(self, position_ms: int) -> None:
        await self._web.seek(position_ms)
        self._state.position_ms = position_ms
        await self._emit()

    async def set_volume(self, volume: int) -> None:
        await self._web.set_volume(volume)
        self._state.volume = volume
        await self._emit()

    # --- background loops ------------------------------------------------------

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(_TICK_MS / 1000)
            if self._state.state is PlaybackState.PLAYING and self._state.track:
                self._state.position_ms = min(
                    self._state.position_ms + _TICK_MS, self._state.track.duration_ms
                )
                await self._emit()

    async def _reconcile_loop(self) -> None:
        while True:
            await asyncio.sleep(_RECONCILE_S)
            with contextlib.suppress(Exception):
                await self._reconcile()

    async def _reconcile(self) -> None:
        """Pull authoritative state from the Web API to correct event/tick drift."""
        playback = await self._web.get_playback()
        if not playback:
            return
        self._state.state = PlaybackState.PLAYING if playback.get("is_playing") else PlaybackState.PAUSED
        if (pos := playback.get("progress_ms")) is not None:
            self._state.position_ms = pos
        item = playback.get("item")
        if item and item.get("id") and item["id"] != self._current_track_id:
            await self._load_track(item["id"], item.get("duration_ms"))
        if (dev := playback.get("device")) and (vol := dev.get("volume_percent")) is not None:
            self._state.volume = vol
        await self._emit()

    async def _emit(self) -> None:
        await self._publish(self.snapshot())
