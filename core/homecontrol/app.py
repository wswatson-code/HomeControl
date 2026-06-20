"""FastAPI application factory.

Owns the lifespan of the `StateManager` (and thus the active provider's background
tasks), mounts the REST + WebSocket routers, and — when present — serves the built
kiosk UI as static files so a unit runs from a single process.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import internal, rest, system, ws
from .config import Settings, settings
from .state import StateManager

# ui/dist relative to repo root (../../ui/dist from this file). Served only if built.
_UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"


def create_app(cfg: Settings | None = None) -> FastAPI:
    cfg = cfg or settings

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        manager = StateManager(cfg)
        app.state.manager = manager
        await manager.start()
        try:
            yield
        finally:
            await manager.stop()

    app = FastAPI(title="HomeControl Core Service", version=__version__, lifespan=lifespan)

    # Dev convenience: the Vite dev server (port 5173) calls the API cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(rest.router)
    app.include_router(ws.router)
    app.include_router(internal.router)
    app.include_router(system.router)

    if _UI_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")

    return app
