"""Spotify playback providers.

`SpotifyProvider` is the interface the rest of the Core Service depends on. Phase 1
ships `MockSpotify` (no hardware/credentials); Phase 2 adds `LibrespotSpotify`, backed
by a systemd-supervised librespot Connect receiver and the Spotify Web API.
"""

from __future__ import annotations

from ..config import Settings
from .base import PublishPlayer, SpotifyProvider
from .mock import MockSpotify

__all__ = ["SpotifyProvider", "MockSpotify", "create_provider"]


def create_provider(name: str, publish: PublishPlayer, settings: Settings) -> SpotifyProvider:
    """Factory selected by `settings.spotify_provider`."""
    if name == "mock":
        return MockSpotify(publish)
    if name == "librespot":
        # Lazy import: keeps httpx (and the Web API client) out of the mock-only path.
        from .librespot import LibrespotSpotify

        return LibrespotSpotify(publish, settings)
    raise ValueError(f"unknown spotify provider {name!r} (expected 'mock' or 'librespot')")
