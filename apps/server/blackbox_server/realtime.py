from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import anyio
from fastapi import WebSocket


class LiveEventHub:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        await websocket.send_json({"type": "connected", "version": self._version})

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        self._version += 1
        message = {
            "version": self._version,
            "emitted_at": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        dead: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


event_hub = LiveEventHub()


def publish_change(message_type: str, **payload: Any) -> None:
    event = {"type": message_type, "payload": payload}
    try:
        anyio.from_thread.run(event_hub.broadcast, event)
        return
    except RuntimeError:
        pass

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(event_hub.broadcast(event))
