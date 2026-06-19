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

from app.api import backtest_routes, routes
from app.core.instruments import get_instrument
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
    settings = get_settings()
    init_db(reset=settings.provider == "mock")
    if settings.provider == "kite":
        log.info("SAFETY: order placement DISABLED — paper trades only, no real capital")
    runner = EngineRunner()  # factory logs the chosen provider
    app.state.runner = runner

    manager.bind(asyncio.get_running_loop())

    async def on_update(state: dict) -> None:
        await manager.broadcast({"type": "state", "data": state})

    runner.on_update = on_update
    log.subscribe(lambda entry: manager.push({"type": "log", "data": entry}))

    task = asyncio.create_task(runner.run())
    async def live_quotes() -> None:
        while True:
            try:
                instruments = [get_instrument(k) for k in sorted(runner.enabled)]
                ticks = runner.provider.live_snapshot(instruments, runner.broker.open_positions())
                await manager.broadcast({"type": "live_ticks", "data": ticks})
            except Exception as e:
                log.error(f"live quote broadcast failed: {e}")
            await asyncio.sleep(3)

    live_task = asyncio.create_task(live_quotes())
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        task.cancel()
        live_task.cancel()


app = FastAPI(title="Options Paper Trader", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes.router)
app.include_router(backtest_routes.router)


@app.get("/api/health")
def health():
    return {"ok": True}
