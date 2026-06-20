"""SpotifyWebClient unit tests — device resolution + track normalization (no network)."""

from __future__ import annotations

from homecontrol.models import Device
from homecontrol.spotify.web import SpotifyWebClient, _to_track


def _client(name="Living Room"):
    return SpotifyWebClient("id", "secret", "refresh", name)


async def test_resolve_keeps_available_requested_device(monkeypatch):
    c = _client()

    async def devices():
        return [Device(id="d1", name="Phone"), Device(id="local", name="Living Room")]

    monkeypatch.setattr(c, "list_devices", devices)
    assert await c.resolve_device_id("d1") == "d1"
    await c.aclose()


async def test_resolve_falls_back_to_local_when_none(monkeypatch):
    c = _client()

    async def devices():
        return [Device(id="local", name="Living Room")]

    monkeypatch.setattr(c, "list_devices", devices)
    assert await c.resolve_device_id(None) == "local"
    await c.aclose()


async def test_resolve_falls_back_when_requested_offline(monkeypatch):
    c = _client()

    async def devices():
        return [Device(id="local", name="Living Room")]

    monkeypatch.setattr(c, "list_devices", devices)
    assert await c.resolve_device_id("stale-id") == "local"
    await c.aclose()


async def test_resolve_none_when_no_local_present(monkeypatch):
    c = _client()

    async def devices():
        return [Device(id="d1", name="Phone")]

    monkeypatch.setattr(c, "list_devices", devices)
    assert await c.resolve_device_id(None) is None  # Spotify uses the active device
    await c.aclose()


def test_to_track_handles_episode_without_artists():
    # Podcast episode / malformed row: no artists, no album — must not raise.
    t = _to_track({"id": "e1", "name": "Episode", "artists": None, "album": None})
    assert t.id == "e1" and t.artist == "" and t.album == ""


def test_to_track_normal():
    t = _to_track(
        {
            "id": "t1",
            "name": "Song",
            "artists": [{"name": "A"}, {"name": "B"}],
            "album": {"name": "Alb", "images": [{"url": "u"}]},
            "duration_ms": 1000,
        }
    )
    assert t.artist == "A, B" and t.album == "Alb" and t.artwork_url == "u"
