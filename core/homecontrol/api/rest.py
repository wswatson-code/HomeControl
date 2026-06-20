"""REST control routes.

Thin: every route validates input, calls into the provider/state, and returns the new
snapshot. Realtime updates flow over /ws, so clients can fire-and-forget these and let
the socket reconcile.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..models import CreateTimerBody, PlayBody, SeekBody, Snapshot, TransferBody, VolumeBody
from ..spotify.web import SpotifyWebClient
from ..state import StateManager

router = APIRouter(prefix="/api", tags=["control"])


def _state(request: Request) -> StateManager:
    return request.app.state.manager


def _catalog(request: Request) -> SpotifyWebClient:
    cat = _state(request).catalog
    if cat is None:
        raise HTTPException(status_code=503, detail="browsing requires Spotify Web API credentials")
    return cat


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


# ------------------------------------------------------- browse / search / devices
# Catalog endpoints (require Spotify Web API creds; 503 otherwise). They return normalized
# BrowseItem/Track/Device shapes, not raw Spotify JSON.


@router.get("/search")
async def search(request: Request, q: str, types: str = "track,album,artist,playlist", limit: int = 20) -> dict:
    return await _catalog(request).search(q, types, limit)


@router.get("/browse/playlists")
async def browse_playlists(request: Request) -> dict:
    return {"items": await _catalog(request).my_playlists()}


@router.get("/browse/albums")
async def browse_albums(request: Request) -> dict:
    return {"items": await _catalog(request).my_albums()}


@router.get("/browse/playlist/{playlist_id}")
async def browse_playlist(request: Request, playlist_id: str) -> dict:
    return {"tracks": await _catalog(request).playlist_tracks(playlist_id)}


@router.get("/browse/album/{album_id}")
async def browse_album(request: Request, album_id: str) -> dict:
    return {"tracks": await _catalog(request).album_tracks(album_id)}


@router.get("/browse/artist/{artist_id}")
async def browse_artist(request: Request, artist_id: str) -> dict:
    return await _catalog(request).artist(artist_id)


@router.get("/devices")
async def list_devices(request: Request) -> dict:
    return {"devices": await _catalog(request).list_devices()}


@router.post("/play")
async def play_content(request: Request, body: PlayBody) -> dict:
    await _catalog(request).play_context(
        device_id=body.device_id, context_uri=body.context_uri, uris=body.uris, offset=body.offset
    )
    return {"ok": True}


@router.post("/transfer")
async def transfer_playback(request: Request, body: TransferBody) -> dict:
    await _catalog(request).transfer(body.device_id, body.play)
    return {"ok": True}
