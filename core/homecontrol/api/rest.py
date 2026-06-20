"""REST control routes.

Thin: every route validates input, calls into the provider/state, and returns the new
snapshot. Realtime updates flow over /ws, so clients can fire-and-forget these and let
the socket reconcile.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..models import CreateTimerBody, SeekBody, Snapshot, VolumeBody
from ..state import StateManager

router = APIRouter(prefix="/api", tags=["control"])


def _state(request: Request) -> StateManager:
    return request.app.state.manager


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/state", response_model=Snapshot)
async def get_state(request: Request) -> Snapshot:
    return _state(request).snapshot()


@router.post("/player/play", response_model=Snapshot)
async def play(request: Request) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.play()
    return mgr.snapshot()


@router.post("/player/pause", response_model=Snapshot)
async def pause(request: Request) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.pause()
    return mgr.snapshot()


@router.post("/player/next", response_model=Snapshot)
async def next_track(request: Request) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.next()
    return mgr.snapshot()


@router.post("/player/previous", response_model=Snapshot)
async def previous_track(request: Request) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.previous()
    return mgr.snapshot()


@router.post("/player/seek", response_model=Snapshot)
async def seek(request: Request, body: SeekBody) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.seek(body.position_ms)
    return mgr.snapshot()


@router.post("/player/volume", response_model=Snapshot)
async def set_volume(request: Request, body: VolumeBody) -> Snapshot:
    mgr = _state(request)
    await mgr.spotify.set_volume(body.volume)
    return mgr.snapshot()


# ------------------------------------------------------------------------------ timers


@router.post("/timer", response_model=Snapshot)
async def create_timer(request: Request, body: CreateTimerBody) -> Snapshot:
    mgr = _state(request)
    await mgr.timers.create(body.duration_ms, body.label)
    return mgr.snapshot()


@router.delete("/timer/{timer_id}", response_model=Snapshot)
async def dismiss_timer(request: Request, timer_id: str) -> Snapshot:
    mgr = _state(request)
    if not await mgr.timers.dismiss(timer_id):
        raise HTTPException(status_code=404, detail=f"no timer {timer_id!r}")
    return mgr.snapshot()
