"""The realtime event stream.

On connect a client gets a full `snapshot` event, then a live feed of deltas. This is
the primary channel the kiosk and mobile apps use to stay in sync; REST is for commands.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..models import Event, EventType
from ..state import StateManager

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    manager: StateManager = websocket.app.state.manager

    # Snapshot first so a fresh client renders immediately without a REST round-trip.
    snapshot = Event(type=EventType.SNAPSHOT, data=manager.snapshot().model_dump(mode="json"))
    await websocket.send_text(snapshot.model_dump_json())

    async with manager.bus.subscribe() as queue:
        try:
            while True:
                event = await queue.get()
                await websocket.send_text(event.model_dump_json())
        except WebSocketDisconnect:
            return
