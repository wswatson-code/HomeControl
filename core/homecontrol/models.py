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
    version: str


# ----------------------------------------------------------------- command bodies


class VolumeBody(BaseModel):
    volume: int = Field(ge=0, le=100)


class SeekBody(BaseModel):
    position_ms: int = Field(ge=0)


# --------------------------------------------------------------- websocket events


class EventType(StrEnum):
    SNAPSHOT = "snapshot"  # full state (sent once on connect)
    PLAYER = "player"  # PlayerState changed
    UNIT = "unit"  # UnitInfo changed


class Event(BaseModel):
    """Realtime push over /ws. `data` shape depends on `type`."""

    type: EventType
    data: dict
