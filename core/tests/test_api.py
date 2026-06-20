"""Phase 1 smoke tests: the API contract and the mock provider behave."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from homecontrol.app import create_app
from homecontrol.config import Settings


@pytest.fixture
def client():
    app = create_app(Settings(spotify_provider="mock", unit_id="test", room="Test Room"))
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_state_snapshot_shape(client):
    snap = client.get("/api/state").json()
    assert snap["unit"]["room"] == "Test Room"
    assert snap["player"]["track"]["title"]  # mock playlist loaded
    assert "version" in snap


def test_play_pause_roundtrip(client):
    assert client.post("/api/player/play").json()["player"]["state"] == "playing"
    assert client.post("/api/player/pause").json()["player"]["state"] == "paused"


def test_volume_clamped(client):
    assert client.post("/api/player/volume", json={"volume": 80}).json()["player"]["volume"] == 80
    # out-of-range is rejected by the contract (422), not silently clamped
    assert client.post("/api/player/volume", json={"volume": 999}).status_code == 422


def test_next_changes_track(client):
    before = client.get("/api/state").json()["player"]["track"]["id"]
    after = client.post("/api/player/next").json()["player"]["track"]["id"]
    assert before != after


def test_ws_sends_snapshot_first(client):
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert first["data"]["player"]["track"]["title"]


def test_kiosk_stop_ok(client, monkeypatch):
    # Stub the privileged call so the test never touches systemd.
    import homecontrol.api.system as system

    async def fake_stop():
        return 0, ""

    monkeypatch.setattr(system, "_stop_kiosk", fake_stop)
    assert client.post("/api/system/kiosk/stop").json() == {"ok": True}


def test_kiosk_stop_reports_failure(client, monkeypatch):
    import homecontrol.api.system as system

    async def fake_stop():
        return 1, "Failed to stop homecontrol-kiosk.service: not found"

    monkeypatch.setattr(system, "_stop_kiosk", fake_stop)
    assert client.post("/api/system/kiosk/stop").status_code == 500


def test_kiosk_stop_absent_from_public_contract(client):
    # Device-local controls must stay out of the OpenAPI surface the apps codegen from.
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/system/kiosk/stop" not in paths


# ----------------------------------------------------------------------------- timers


def test_create_timer(client):
    snap = client.post("/api/timer", json={"duration_ms": 60000, "label": "tea"}).json()
    assert len(snap["timers"]) == 1
    t = snap["timers"][0]
    assert t["label"] == "tea"
    assert t["state"] == "running"
    assert t["duration_ms"] == 60000
    assert t["fires_at_ms"] > 0


def test_create_timer_rejects_nonpositive(client):
    assert client.post("/api/timer", json={"duration_ms": 0}).status_code == 422


def test_dismiss_timer(client):
    tid = client.post("/api/timer", json={"duration_ms": 60000}).json()["timers"][0]["id"]
    snap = client.delete(f"/api/timer/{tid}").json()
    assert snap["timers"] == []


def test_dismiss_unknown_timer_404(client):
    assert client.delete("/api/timer/nope").status_code == 404


def test_timer_fires(client):
    # A short timer should flip to FIRED on its own (stays in the list, ringing).
    client.post("/api/timer", json={"duration_ms": 50, "label": "quick"})
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        timers = client.get("/api/state").json()["timers"]
        if timers and timers[0]["state"] == "fired":
            break
        time.sleep(0.05)
    timers = client.get("/api/state").json()["timers"]
    assert timers and timers[0]["state"] == "fired"


# ------------------------------------------------------------------------------ voice


def test_voice_state_internal_updates_snapshot(client):
    r = client.post("/internal/voice/state", json={"phase": "listening", "transcript": ""})
    assert r.json() == {"ok": True}
    assert client.get("/api/state").json()["voice"]["phase"] == "listening"


def test_voice_state_absent_from_public_contract(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/internal/voice/state" not in paths


# ------------------------------------------------------------------------------ browse


from homecontrol.models import BrowseItem, Device, Track  # noqa: E402


class _FakeCatalog:
    def __init__(self):
        self.played = None
        self.transferred = None

    async def my_playlists(self, limit=50):
        return [BrowseItem(id="p1", uri="spotify:playlist:p1", type="playlist", name="Chill")]

    async def my_albums(self, limit=50):
        return [BrowseItem(id="a1", uri="spotify:album:a1", type="album", name="OK Computer")]

    async def playlist_tracks(self, playlist_id, limit=100):
        return [Track(id="t1", title="Song", artist="Band")]

    async def album_tracks(self, album_id, limit=50):
        return [Track(id="t2", title="Track", artist="Band")]

    async def artist(self, artist_id):
        return {"top_tracks": [Track(id="t3", title="Hit", artist="Band")], "albums": []}

    async def search(self, query, types="track,album,artist,playlist", limit=20):
        return {"tracks": [BrowseItem(id="t4", uri="spotify:track:t4", type="track", name="Found")]}

    async def list_devices(self):
        return [Device(id="d1", name="Kitchen", is_active=True)]

    async def play_context(self, *, device_id=None, context_uri=None, uris=None, offset=None):
        self.played = {"device_id": device_id, "context_uri": context_uri, "uris": uris, "offset": offset}

    async def transfer(self, device_id, play=True):
        self.transferred = {"device_id": device_id, "play": play}

    async def aclose(self):  # called by StateManager.stop() on teardown
        pass


@pytest.fixture
def browse_client(client):
    """The mock-provider client has no catalog; inject a fake so browse endpoints work."""
    fake = _FakeCatalog()
    client.app.state.manager.catalog = fake
    return client, fake


def test_browse_requires_catalog(client):
    # No Spotify creds under the mock provider -> catalog is None -> 503.
    assert client.app.state.manager.catalog is None
    assert client.get("/api/browse/playlists").status_code == 503


def test_browse_playlists(browse_client):
    client, _ = browse_client
    items = client.get("/api/browse/playlists").json()["items"]
    assert items[0]["name"] == "Chill" and items[0]["type"] == "playlist"


def test_search(browse_client):
    client, _ = browse_client
    out = client.get("/api/search", params={"q": "found"}).json()
    assert out["tracks"][0]["name"] == "Found"


def test_list_devices(browse_client):
    client, _ = browse_client
    devices = client.get("/api/devices").json()["devices"]
    assert devices[0]["name"] == "Kitchen" and devices[0]["is_active"] is True


def test_play_context_passes_through(browse_client):
    client, fake = browse_client
    r = client.post("/api/play", json={"context_uri": "spotify:playlist:p1", "device_id": "d1"})
    assert r.json() == {"ok": True}
    assert fake.played == {"device_id": "d1", "context_uri": "spotify:playlist:p1", "uris": None, "offset": None}


def test_transfer_passes_through(browse_client):
    client, fake = browse_client
    client.post("/api/transfer", json={"device_id": "d1", "play": True})
    assert fake.transferred == {"device_id": "d1", "play": True}
