"""
FastAPI entrypoint. On startup it initialises the DB, wires the log bus and
engine-state callback into the WebSocket hub, and launches the autonomous engine
loop as a background task. The owner just runs this and watches.

    uvicorn app.main:app --reload        # from the backend/ directory
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import backtest_routes, portfolio_routes, routes
from app.api.auth import extract_token, token_ok
from app.core.instruments import get_instrument
from app.core.config import get_settings
from app.core.logging import log
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.journal import routes as journal_routes
from app.ws.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kite (live) persists the book across restarts, as intended. Mock resets each
    # run: its synthetic clock restarts each process, so a persisted mock position
    # would be mispriced against a different sim-time on the next launch.
    settings = get_settings()
    # C7: refuse to start a second backend against the same persistent (non-mock) DB
    # — two instances would trade the same real account with independent in-flight
    # state. Mock (tests, dry-run) skips this so multiple TestClients can coexist.
    if settings.provider != "mock":
        from app.core.instance_lock import acquire_db_lock
        app.state.db_lock = acquire_db_lock(settings.db_path)
    init_db(reset=settings.provider == "mock")
    if settings.provider == "kite":
        from app.engine.broker_factory import live_execution_enabled
        if live_execution_enabled():
            log.warn("🔴 LIVE MODE — real Kite orders are ENABLED (still gated by ARM; "
                     "disarmed on every start). Use the KILL switch to square off.")
        else:
            log.info("SAFETY: order placement DISABLED — paper trades only, no real capital")
    # Reconstruct any deployed generated strategies from the DB and register them BEFORE
    # the runner loads per-instrument config, so a gen_* watchlist assignment resolves to
    # the real strategy instead of the default fallback. Non-fatal: a bad row is skipped.
    # Frozen behind PT_RESEARCH_ENABLED: with the research plane off nothing registers,
    # and a stale gen_* assignment fail-safes to the default strategy (registry fallback).
    if settings.research_enabled:
        try:
            from app.core.generated_strategies import register_all
            from app.db.session import SessionLocal
            with SessionLocal() as s:
                register_all(s)
        except Exception as e:
            log.error(f"generated-strategy registration failed at startup: {e}")
    else:
        log.info("research plane disabled (PT_RESEARCH_ENABLED=0) — generated strategies "
                 "not registered; portfolio/research API is gated off")
    runner = EngineRunner()  # factory logs the chosen provider
    app.state.runner = runner

    manager.bind(asyncio.get_running_loop())

    async def on_update(state: dict) -> None:
        await manager.broadcast({"type": "state", "data": state})

    async def on_position_ticks(ticks: dict) -> None:
        await manager.broadcast({"type": "position_ticks", "data": ticks})

    runner.on_update = on_update
    runner.on_position_ticks = on_position_ticks
    log.subscribe(lambda entry: manager.push({"type": "log", "data": entry}))

    # Two cooperative lanes: the fast risk loop marks open positions + ratchets
    # the trailing stop (and feeds position_ticks); the signal loop scans for
    # entries on completed candles. The old single-cadence live_quotes task is
    # gone — the risk loop now produces the live UI position feed.
    runner.running = True
    # H13: replay the persisted order journal BEFORE the loops start — a crash in the
    # order-poll window leaves in-flight orders whose in-memory tracking was wiped;
    # recovery adopts late fills / books filled exits so a restart resumes mid-flight.
    # Must finish before the signal loop can re-enter an instrument. Non-fatal.
    try:
        await asyncio.to_thread(runner.broker.recover_journal, runner.provider.now())
    except Exception as e:
        log.error(f"order journal recovery failed at startup: {e}")
    signal_task = asyncio.create_task(runner.run_signal_loop())
    risk_task = asyncio.create_task(runner.run_risk_loop())
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        signal_task.cancel()
        risk_task.cancel()


class _PollingRouteFilter(logging.Filter):
    """Demote high-frequency UI polling GETs out of the access log (2026-07-15
    autopsy: ~34% of the 3-day journal was polling noise). Real mutating/rare
    routes still log normally."""
    _NOISY = ("/api/execution/state", "/api/status", "/api/signals")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f"GET {p} " in msg for p in self._NOISY)


logging.getLogger("uvicorn.access").addFilter(_PollingRouteFilter())

app = FastAPI(title="Options Paper Trader", lifespan=lifespan)

_AUTH_EXEMPT_PATHS = {"/api/health", "/api/login", "/api/session"}


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """SEC-1: gate every /api/* call behind PT_API_TOKEN. Empty token (the
    default) disables auth entirely — dev/mock/tests are unaffected. Exempt
    even with a token configured: /api/health (uptime probe) and the Kite
    OAuth redirect endpoints (/api/login, /api/session — the browser hits
    these directly and can't attach a header), plus CORS preflight (OPTIONS)
    and anything outside /api."""
    settings = get_settings()
    path = request.url.path
    if (
        settings.api_token
        and path.startswith("/api")
        and path not in _AUTH_EXEMPT_PATHS
        and request.method != "OPTIONS"
    ):
        if not token_ok(extract_token(request.headers)):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


# CORSMiddleware is registered AFTER auth_gate above so it ends up OUTERMOST
# (Starlette wraps middleware in reverse-of-registration order): a 401 minted
# by auth_gate still passes back out through CORS and gets its headers
# attached, and a preflight OPTIONS is answered by CORS before it ever
# reaches auth_gate.
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origins_list, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes.router)
app.include_router(backtest_routes.router)
app.include_router(portfolio_routes.router)
app.include_router(journal_routes.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# ── production: serve the built React SPA from the same origin ──────────────
# Registered LAST so the API routers and /api/health match first. Off unless
# PT_SERVE_FRONTEND=1 and PT_FRONTEND_DIST points at a real dist/ directory.
# (Restored 2026-07-18: this block lived only on feat/vps-deploy and was lost
# when feat/exits-journal was deployed whole-tree over the VPS — see 6cb92c8.)
_spa_settings = get_settings()
if _spa_settings.serve_frontend and os.path.isdir(_spa_settings.frontend_dist):
    _DIST = _spa_settings.frontend_dist
    _ASSETS = os.path.join(_DIST, "assets")
    if os.path.isdir(_ASSETS):
        app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Never hijack the API or WebSocket surfaces.
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("ws"):
            return JSONResponse({"error": "not found"}, status_code=404)
        candidate = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
