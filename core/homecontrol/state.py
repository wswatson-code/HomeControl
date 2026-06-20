"""The unit's single source of truth.

Owns `UnitInfo`, the active Spotify provider, and the `EventBus`. Subsystems mutate
state through here; mutations publish typed events that the WebSocket layer (and, later,
the inter-unit mesh) fan out. The HTTP layer never touches a provider directly.
"""

from __future__ import annotations

from . import __version__
from .config import Settings
from .events import EventBus
from .models import Event, EventType, PlayerState, Snapshot, TimerInfo, UnitInfo, VoiceState
from .spotify import SpotifyProvider, create_provider
from .timers import TimerManager


class StateManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.bus = EventBus()
        self.unit = UnitInfo(id=settings.unit_id, room=settings.room)
        self.spotify: SpotifyProvider = create_provider(
            settings.spotify_provider, self._on_player_changed, settings
        )
        self.timers = TimerManager(self._on_timers_changed)
        # The voice pipeline (a separate service) reports its phase here for the kiosk
        # overlay; idle until it connects.
        self.voice = VoiceState()

    async def start(self) -> None:
        await self.spotify.start()

    async def stop(self) -> None:
        await self.spotify.stop()
        await self.timers.stop()

    def snapshot(self) -> Snapshot:
        return Snapshot(
            unit=self.unit,
            player=self.spotify.snapshot(),
            timers=self.timers.list(),
            voice=self.voice,
            version=__version__,
        )

    async def handle_spotify_event(self, env: dict[str, str]) -> None:
        """Route a librespot --onevent payload to the provider, if it accepts events."""
        handler = getattr(self.spotify, "handle_event", None)
        if handler is not None:
            await handler(env)

    async def set_voice_state(self, voice: VoiceState) -> None:
        """Called by the voice service (via /internal) so the kiosk can show what it heard."""
        self.voice = voice
        await self.bus.publish(Event(type=EventType.VOICE, data=voice.model_dump(mode="json")))

    async def _on_player_changed(self, player: PlayerState) -> None:
        await self.bus.publish(Event(type=EventType.PLAYER, data=player.model_dump(mode="json")))

    async def _on_timers_changed(self, timers: list[TimerInfo]) -> None:
        data = {"timers": [t.model_dump(mode="json") for t in timers]}
        await self.bus.publish(Event(type=EventType.TIMERS, data=data))
