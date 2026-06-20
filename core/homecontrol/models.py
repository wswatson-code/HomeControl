"""The HomeControl API contract.

These Pydantic models ARE the public contract consumed by both the kiosk web app and
the Flutter mobile app. FastAPI exports them to OpenAPI (`/openapi.json`), which is the
source of truth for client codegen. Treat changes here as API changes: additive where
possible, versioned when breaking.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- enums


class PlaybackState(StrEnum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    BUFFERING = "buffering"


class RepeatMode(StrEnum):
    OFF = "off"
    TRACK = "track"
    CONTEXT = "context"


# -------------------------------------------------------------------------- player


class Track(BaseModel):
    id: str
    title: str
    artist: str
    album: str = ""
    artwork_url: str | None = None
    duration_ms: int = 0


class PlayerState(BaseModel):
    """Everything the now-playing screen needs."""

    state: PlaybackState = PlaybackState.STOPPED
    track: Track | None = None
    position_ms: int = 0
    volume: int = Field(default=50, ge=0, le=100)
    shuffle: bool = False
    repeat: RepeatMode = RepeatMode.OFF


# --------------------------------------------------------------------------- timers


class TimerState(StrEnum):
    RUNNING = "running"
    FIRED = "fired"  # elapsed; stays in the list (ringing) until dismissed


class TimerInfo(BaseModel):
    """A countdown timer or alarm. `fires_at_ms` is a Unix epoch so the UI can count
    down locally between server ticks (like player position), no polling needed."""

    id: str
    label: str = ""
    duration_ms: int  # original requested duration
    fires_at_ms: int  # Unix epoch ms when it fires
    state: TimerState = TimerState.RUNNING


# ---------------------------------------------------------------------------- voice


class VoicePhase(StrEnum):
    IDLE = "idle"  # waiting for the wake word
    LISTENING = "listening"  # wake word heard, capturing the command
    THINKING = "thinking"  # running STT + intent
    SPEAKING = "speaking"  # TTS reply playing


class VoiceState(BaseModel):
    """What the voice pipeline is doing — drives the kiosk's listening overlay."""

    phase: VoicePhase = VoicePhase.IDLE
    transcript: str = ""  # last recognized command
    reply: str = ""  # last spoken reply


# --------------------------------------------------------------------------- browse


class BrowseItem(BaseModel):
    """A normalized catalog entry (playlist/album/artist/track) for the browse UI —
    deliberately small, not raw Spotify JSON, so the contract and the kiosk stay lean."""

    id: str
    uri: str  # spotify:playlist:… / album / artist / track — what you hand to /api/play
    type: str  # playlist | album | artist | track
    name: str
    subtitle: str = ""  # owner / artist(s) / etc.
    image: str | None = None


class Device(BaseModel):
    """A Spotify Connect device the user can target for playback."""

    id: str
    name: str
    type: str = ""
    is_active: bool = False
    volume: int | None = None


# ---------------------------------------------------------------------------- unit


class GroupRole(StrEnum):
    SOLO = "solo"  # a group of one
    LEADER = "leader"  # hosts the Snapcast server for its group
    MEMBER = "member"  # snapclient following a leader


class UnitInfo(BaseModel):
    """Identity + multi-room role of this physical unit."""

    id: str  # stable per-device id
    room: str  # friendly name, e.g. "Kitchen"
    group_id: str | None = None  # the multi-room group this unit belongs to
    role: GroupRole = GroupRole.SOLO


class Snapshot(BaseModel):
    """Full state returned by GET /api/state and pushed on WS connect."""

    unit: UnitInfo
    player: PlayerState
    timers: list[TimerInfo] = Field(default_factory=list)
    voice: VoiceState = Field(default_factory=VoiceState)
    version: str


# ----------------------------------------------------------------- command bodies


class VolumeBody(BaseModel):
    volume: int = Field(ge=0, le=100)


class SeekBody(BaseModel):
    position_ms: int = Field(ge=0)


class CreateTimerBody(BaseModel):
    duration_ms: int = Field(gt=0)
    label: str = ""


class PlayBody(BaseModel):
    """Start playback. Either a context (playlist/album/artist uri) or explicit track uris;
    device_id picks the target (omitted = the user's current/active device)."""

    device_id: str | None = None
    context_uri: str | None = None
    uris: list[str] | None = None
    offset: int | None = Field(default=None, ge=0)  # index into the context/uris


class TransferBody(BaseModel):
    device_id: str
    play: bool = True


# --------------------------------------------------------------- websocket events


class EventType(StrEnum):
    SNAPSHOT = "snapshot"  # full state (sent once on connect)
    PLAYER = "player"  # PlayerState changed
    UNIT = "unit"  # UnitInfo changed
    TIMERS = "timers"  # the active-timer list changed (created/fired/dismissed)
    VOICE = "voice"  # VoiceState changed (listening overlay)


class Event(BaseModel):
    """Realtime push over /ws. `data` shape depends on `type`."""

    type: EventType
    data: dict
