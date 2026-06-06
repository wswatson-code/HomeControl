"""Internal endpoints — called by local helper processes, not by UI clients.

The librespot `--onevent` hook script (provisioning/spotify/onevent.sh) POSTs the
event's environment here on every player event. Localhost-only by intent; later phases
add per-unit auth. Kept off the public `/api` surface so it never leaks into the
OpenAPI contract the apps consume.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..state import StateManager

# include_in_schema=False keeps these routes out of /openapi.json — the apps codegen
# from that contract and must never see internal endpoints.
router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@router.post("/spotify/event")
async def spotify_event(request: Request, env: dict[str, str]) -> dict:
    manager: StateManager = request.app.state.manager
    await manager.handle_spotify_event(env)
    return {"ok": True}
