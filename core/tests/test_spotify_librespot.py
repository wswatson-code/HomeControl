"""Phase 2: librespot event parsing + provider state transitions (no network)."""

from __future__ import annotations

import pytest

from homecontrol.config import Settings
from homecontrol.models import PlaybackState, Track
from homecontrol.spotify import create_provider
from homecontrol.spotify.librespot import LibrespotSpotify, parse_player_event

# --- pure event parsing ---------------------------------------------------------


def test_parse_changed_event():
    ev = parse_player_event(
        {"PLAYER_EVENT": "changed", "TRACK_ID": "abc123", "DURATION_MS": "200000", "POSITION_MS": "0"}
    )
    assert ev.kind == "changed"
    assert ev.track_id == "abc123"
    assert ev.duration_ms == 200000


def test_parse_no_event_returns_none():
    assert parse_player_event({"TRACK_ID": "abc"}) is None


@pytest.mark.parametrize(
    "raw,expected",
    [("32768", 50), ("65535", 100), ("0", 0), ("40", 40), ("100", 100)],
)
def test_volume_normalization(raw, expected):
    ev = parse_player_event({"PLAYER_EVENT": "volume", "VOLUME": raw})
    assert ev.volume == expected


# --- provider transitions with a stubbed Web client -----------------------------


class _StubWeb:
    """Stands in for SpotifyWebClient — no network, records control calls."""

    def __init__(self):
        self.calls: list[str] = []

    async def device_id(self, refresh=False):
        return "dev1"

    async def get_playback(self):
        return None

    async def get_track(self, track_id):
        return Track(id=track_id, title="Song", artist="Artist", album="Album", duration_ms=200000)

    async def aclose(self):
        pass

    def __getattr__(self, name):
        async def _record(*a, **k):
            self.calls.append(name)

        return _record


@pytest.fixture
def provider():
    p = LibrespotSpotify(publish=_noop_publish, settings=Settings(spotify_provider="librespot"))
    p._web = _StubWeb()
    return p


async def _noop_publish(state):
    pass


async def test_changed_loads_track_and_plays(provider):
    await provider.handle_event({"PLAYER_EVENT": "changed", "TRACK_ID": "t9", "DURATION_MS": "200000"})
    snap = provider.snapshot()
    assert snap.state is PlaybackState.PLAYING
    assert snap.track.id == "t9"
    assert snap.track.title == "Song"
    assert snap.position_ms == 0


async def test_pause_then_stop(provider):
    await provider.handle_event({"PLAYER_EVENT": "changed", "TRACK_ID": "t1"})
    await provider.handle_event({"PLAYER_EVENT": "paused", "POSITION_MS": "5000"})
    assert provider.snapshot().state is PlaybackState.PAUSED
    assert provider.snapshot().position_ms == 5000
    await provider.handle_event({"PLAYER_EVENT": "stopped"})
    assert provider.snapshot().state is PlaybackState.STOPPED


async def test_volume_event_updates_state(provider):
    await provider.handle_event({"PLAYER_EVENT": "volume", "VOLUME": "65535"})
    assert provider.snapshot().volume == 100


async def test_transport_delegates_to_web(provider):
    await provider.next()
    await provider.set_volume(30)
    assert "next" in provider._web.calls
    assert "set_volume" in provider._web.calls
    assert provider.snapshot().volume == 30


# --- factory --------------------------------------------------------------------


def test_factory_builds_librespot_without_network():
    p = create_provider("librespot", _noop_publish, Settings(spotify_provider="librespot"))
    assert isinstance(p, LibrespotSpotify)


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="unknown spotify provider"):
        create_provider("nope", _noop_publish, Settings())
