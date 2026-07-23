"""
Broadcast hub for the main live channel (/ws): engine state snapshots each tick
plus every log line. Per-instrument tick streams (/ws/instrument/{key}) are
handled directly in the route since they're 1:1 and on-demand.

Rewritten after the 2026-07-23 outage: the old hub awaited each client's send
inline (one slow client stalled the engine callbacks) and spawned a coroutine
per log line via run_coroutine_threadsafe, so a slow/stalled dashboard client
made full-state snapshots pile up unboundedly (+100MB/min RSS → VPS OOM).

Now producers only ever enqueue (never touch client I/O):
  - "state"/"position_ticks" coalesce latest-wins — a slow client skips straight
    to the newest snapshot instead of replaying a backlog of stale ones
  - log lines go into a bounded per-client deque (oldest dropped)
  - one sender task per client drains the queue; a send that doesn't complete
    within SEND_TIMEOUT means the client is dead/stalled → it is evicted
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from fastapi import WebSocket

# message types where only the newest matters — stale ones are dropped
_COALESCE = ("state", "position_ticks")


@dataclass
class _Client:
    latest: dict[str, dict] = field(default_factory=dict)   # latest-wins slots
    logs: deque = None  # bounded FIFO for everything else  # type: ignore[assignment]
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class WSManager:
    SEND_TIMEOUT = 10.0  # s — a client that can't take one message in this long is evicted
    LOG_BUFFER = 200     # per-client cap on queued non-coalescable messages

    def __init__(self) -> None:
        self.clients: dict[WebSocket, _Client] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    # ── introspection (tests / diagnostics) ─────────────────────────────────
    def client_count(self) -> int:
        return len(self.clients)

    def pending_count(self, ws: WebSocket) -> int:
        c = self.clients.get(ws)
        return len(c.latest) + len(c.logs) if c else 0

    # ── connection lifecycle ────────────────────────────────────────────────
    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        client = _Client(logs=deque(maxlen=self.LOG_BUFFER))
        self.clients[ws] = client
        client.task = asyncio.get_running_loop().create_task(self._sender(ws, client))

    def disconnect(self, ws: WebSocket) -> None:
        client = self.clients.pop(ws, None)
        if client and client.task and client.task is not asyncio.current_task():
            client.task.cancel()

    # ── producers: enqueue only, never block on client I/O ──────────────────
    def _enqueue(self, msg: dict) -> None:
        for client in self.clients.values():
            if msg.get("type") in _COALESCE:
                client.latest[msg["type"]] = msg
            else:
                client.logs.append(msg)  # bounded: oldest silently dropped
            client.wake.set()

    async def broadcast(self, msg: dict) -> None:
        """Async for call-site compatibility; returns without touching sockets."""
        self._enqueue(msg)

    def push(self, msg: dict) -> None:
        """Thread/loop-safe fire-and-forget broadcast (used by the log bus).
        One cheap callback per message — no coroutine, no unbounded futures."""
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self._enqueue, msg)

    # ── per-client sender ───────────────────────────────────────────────────
    async def _sender(self, ws: WebSocket, client: _Client) -> None:
        try:
            while True:
                await client.wake.wait()
                client.wake.clear()
                batch: list[dict] = []
                for t in _COALESCE:
                    m = client.latest.pop(t, None)
                    if m is not None:
                        batch.append(m)
                while client.logs:
                    batch.append(client.logs.popleft())
                for msg in batch:
                    await asyncio.wait_for(ws.send_json(msg), self.SEND_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            # timeout, closed socket, serialization error — evict this client
            self.clients.pop(ws, None)
            try:
                await ws.close()
            except Exception:
                pass


manager = WSManager()
