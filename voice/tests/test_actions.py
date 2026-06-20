"""Dispatch tests — drive a fake Core Service with httpx MockTransport (no network, no Pi)."""

from __future__ import annotations

import httpx
import pytest

from homecontrol_voice.actions import Actions, _format_duration
from homecontrol_voice.intent import Intent, IntentKind


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://core")


@pytest.mark.asyncio
async def test_play_calls_endpoint():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c).dispatch(Intent(IntentKind.PLAY))
    assert ("POST", "/api/player/play") in calls
    assert reply == "Playing"


@pytest.mark.asyncio
async def test_set_volume_passes_value():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/player/volume":
            import json
            seen.update(json.loads(req.content))
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c).dispatch(Intent(IntentKind.SET_VOLUME, {"volume": 30}))
    assert seen == {"volume": 30}
    assert reply == "Volume 30"


@pytest.mark.asyncio
async def test_volume_up_reads_then_sets():
    posted = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/api/state":
            return httpx.Response(200, json={"player": {"volume": 40}})
        if req.url.path == "/api/player/volume":
            import json
            posted.update(json.loads(req.content))
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c, volume_step=10).dispatch(Intent(IntentKind.VOLUME_UP))
    assert posted == {"volume": 50}
    assert reply == "Volume 50"


@pytest.mark.asyncio
async def test_volume_up_clamps_at_100():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, json={"player": {"volume": 95}})
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c, volume_step=10).dispatch(Intent(IntentKind.VOLUME_UP))
    assert reply == "Volume 100"


@pytest.mark.asyncio
async def test_create_timer_posts_duration():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/timer":
            import json
            seen.update(json.loads(req.content))
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c).dispatch(
            Intent(IntentKind.CREATE_TIMER, {"duration_ms": 600_000, "label": "tea"})
        )
    assert seen == {"duration_ms": 600_000, "label": "tea"}
    assert "10 minutes" in reply


@pytest.mark.asyncio
async def test_unknown_apologizes_without_calling():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        reply = await Actions(c).dispatch(Intent(IntentKind.UNKNOWN))
    assert calls == []
    assert "didn't catch" in reply


@pytest.mark.asyncio
async def test_report_state_swallows_errors():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("core down")

    async with _client(handler) as c:
        await Actions(c).report_state("listening")  # must not raise


@pytest.mark.parametrize(
    "ms,text",
    [
        (600_000, "10 minutes"),
        (3_600_000, "1 hour"),
        (5_400_000, "1 hour 30 minutes"),
        (90_000, "1 minute 30 seconds"),
        (1000, "1 second"),
    ],
)
def test_format_duration(ms, text):
    assert _format_duration(ms) == text
