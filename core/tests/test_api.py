"""Phase 1 smoke tests: the API contract and the mock provider behave."""

from __future__ import annotations

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
