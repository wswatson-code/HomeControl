"""Turn an Intent into Core Service API calls, and report voice state for the kiosk overlay.

The voice service is just another API client (like the mobile app): it drives playback and
timers through the public /api, and POSTs its phase/transcript to /internal/voice/state so
the kiosk can show a "listening…" overlay. Returns a short spoken reply for each action,
which the pipeline hands to Piper.
"""

from __future__ import annotations

import httpx

from .intent import Intent, IntentKind


def _format_duration(ms: int) -> str:
    total = ms // 1000
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    return " ".join(parts) or "0 seconds"


class Actions:
    def __init__(self, client: httpx.AsyncClient, volume_step: int = 10) -> None:
        self._client = client
        self._volume_step = volume_step

    async def report_state(self, phase: str, transcript: str = "", reply: str = "") -> None:
        """Best-effort UI update; never let a reporting failure break the pipeline."""
        try:
            await self._client.post(
                "/internal/voice/state",
                json={"phase": phase, "transcript": transcript, "reply": reply},
            )
        except httpx.HTTPError:
            pass

    async def dispatch(self, intent: Intent) -> str:
        """Execute the intent; return the text to speak back."""
        kind = intent.kind
        if kind is IntentKind.PLAY:
            await self._post("/api/player/play")
            return "Playing"
        if kind is IntentKind.PAUSE:
            await self._post("/api/player/pause")
            return "Paused"
        if kind is IntentKind.NEXT:
            await self._post("/api/player/next")
            return "Next track"
        if kind is IntentKind.PREVIOUS:
            await self._post("/api/player/previous")
            return "Going back"
        if kind is IntentKind.SET_VOLUME:
            vol = int(intent.args["volume"])
            await self._post("/api/player/volume", {"volume": vol})
            return "Muted" if vol == 0 else f"Volume {vol}"
        if kind in (IntentKind.VOLUME_UP, IntentKind.VOLUME_DOWN):
            return await self._nudge_volume(up=kind is IntentKind.VOLUME_UP)
        if kind is IntentKind.CREATE_TIMER:
            ms = int(intent.args["duration_ms"])
            label = intent.args.get("label", "")
            await self._post("/api/timer", {"duration_ms": ms, "label": label})
            spoken = _format_duration(ms)
            return f"Timer set for {spoken}" + (f" for {label}" if label else "")
        return "Sorry, I didn't catch that"

    async def _nudge_volume(self, *, up: bool) -> str:
        # Relative change needs the current value first.
        snap = (await self._client.get("/api/state")).json()
        current = int(snap["player"]["volume"])
        target = max(0, min(100, current + (self._volume_step if up else -self._volume_step)))
        await self._post("/api/player/volume", {"volume": target})
        return f"Volume {target}"

    async def _post(self, path: str, json: dict | None = None) -> None:
        await self._client.post(path, json=json)
