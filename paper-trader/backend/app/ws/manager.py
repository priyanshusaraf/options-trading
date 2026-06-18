"""
Broadcast hub for the main live channel (/ws): engine state snapshots each tick
plus every log line. Per-instrument tick streams (/ws/instrument/{key}) are
handled directly in the route since they're 1:1 and on-demand.
"""
from __future__ import annotations

import asyncio

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, msg: dict) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:
                self.disconnect(ws)

    def push(self, msg: dict) -> None:
        """Thread/loop-safe fire-and-forget broadcast (used by the log bus)."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(msg), self.loop)


manager = WSManager()
