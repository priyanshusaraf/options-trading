"""
FastAPI entrypoint. On startup it initialises the DB, wires the log bus and
engine-state callback into the WebSocket hub, and launches the autonomous engine
loop as a background task. The owner just runs this and watches.

    uvicorn app.main:app --reload        # from the backend/ directory
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.core.config import get_settings
from app.core.logging import log
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.ws.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kite (live) persists the book across restarts, as intended. Mock resets each
    # run: its synthetic clock restarts each process, so a persisted mock position
    # would be mispriced against a different sim-time on the next launch.
    init_db(reset=get_settings().provider == "mock")
    runner = EngineRunner()
    app.state.runner = runner

    manager.bind(asyncio.get_running_loop())

    async def on_update(state: dict) -> None:
        await manager.broadcast({"type": "state", "data": state})

    runner.on_update = on_update
    log.subscribe(lambda entry: manager.push({"type": "log", "data": entry}))

    task = asyncio.create_task(runner.run())
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        task.cancel()


app = FastAPI(title="Options Paper Trader", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes.router)


@app.get("/api/health")
def health():
    return {"ok": True}
