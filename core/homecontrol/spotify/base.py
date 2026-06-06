"""The provider interface the Core Service depends on.

A provider owns playback and reports the current `PlayerState` by calling the `publish`
callback whenever it changes. The state manager wires `publish` to fan state out over
the event bus, so the UI never talks to a provider directly.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable

from ..models import PlayerState

PublishPlayer = Callable[[PlayerState], Awaitable[None]]


class SpotifyProvider(abc.ABC):
    def __init__(self, publish: PublishPlayer) -> None:
        self._publish = publish

    async def start(self) -> None:  # noqa: B027 — optional hook; default no-op is intentional
        """Begin background work (position ticking, Connect registration, ...)."""

    async def stop(self) -> None:  # noqa: B027 — optional hook; default no-op is intentional
        """Tear down background work cleanly."""

    @abc.abstractmethod
    def snapshot(self) -> PlayerState:
        """Current player state, synchronously (used for GET /api/state)."""

    @abc.abstractmethod
    async def play(self) -> None: ...

    @abc.abstractmethod
    async def pause(self) -> None: ...

    @abc.abstractmethod
    async def next(self) -> None: ...

    @abc.abstractmethod
    async def previous(self) -> None: ...

    @abc.abstractmethod
    async def seek(self, position_ms: int) -> None: ...

    @abc.abstractmethod
    async def set_volume(self, volume: int) -> None: ...
