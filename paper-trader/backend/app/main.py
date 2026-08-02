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
from app.api.principal import resolve_http_principal
from app.api.versioning import VERSION_PREFIX, mount_versioned, unversioned_path
from app.core.instruments import get_instrument
from app.core.config import assert_boot_config, get_settings
from app.core.logging import log
from app.core.version import get_build_info, log_build_banner
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.ledger import routes as ledger_routes
from app.ws.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kite (live) persists the book across restarts, as intended. Mock resets each
    # run: its synthetic clock restarts each process, so a persisted mock position
    # would be mispriced against a different sim-time on the next launch.
    settings = get_settings()
    # First thing in the log: which commit is this. Everything below — and every
    # trade this process books — is attributable to it.
    log_build_banner()
    # Before ANY of it: prove this process actually read its configuration. A
    # stray `import pytest` anywhere in the venv detaches `.env`, at which point
    # PT_PROVIDER falls back to "mock" and the engine trades a synthetic market
    # with /api/health returning 200 the whole time. Raising here is the point —
    # a config-less boot must be a dead process, not a healthy-looking one.
    assert_boot_config(settings)
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
    # Journal: detect trades the OWNER placed by hand on the Kite account and
    # file them for reasoning. A third lane on purpose — it reads the orderbook
    # and writes only to ledger.db, never to positions/trades, and it never
    # takes runner._lock (see the 2026-07-13 risk_loop_stalled incident). If it
    # dies, trading is entirely unaffected.
    from app.db.session import SessionLocal
    from app.ledger.db import get_sessionmaker as ledger_sessionmaker
    from app.ledger.lane import run_manual_detect_loop
    detect_task = asyncio.create_task(run_manual_detect_loop(
        runner.provider, SessionLocal, ledger_sessionmaker(),
        get_settings(), runner.provider.now))
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        signal_task.cancel()
        risk_task.cancel()
        detect_task.cancel()
        # Close the broker's long-lived session AFTER the lanes are cancelled,
        # never before: closing it out from under a mid-iteration lane would turn
        # a clean shutdown into an exception in the risk loop. Best-effort — a
        # failure here must not stop the process exiting.
        try:
            runner.broker.close()
        except Exception as e:
            log.warn(f"broker session close failed at shutdown: {e}")


class _PollingRouteFilter(logging.Filter):
    """Demote high-frequency UI polling GETs out of the access log (2026-07-15
    autopsy: ~34% of the 3-day journal was polling noise). Real mutating/rare
    routes still log normally."""
    _NOISY = ("/api/execution/state", "/api/status", "/api/signals")
    # Both surfaces, or the filter silently stops working the day the SPA moves
    # to /api/v1 and the access log fills up again for no visible reason.
    _NOISY_PATHS = tuple(_NOISY) + tuple(
        f"{VERSION_PREFIX}{p[len('/api'):]}" for p in _NOISY)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f"GET {p} " in msg for p in self._NOISY_PATHS)


logging.getLogger("uvicorn.access").addFilter(_PollingRouteFilter())

app = FastAPI(title="Options Paper Trader", lifespan=lifespan)

_AUTH_EXEMPT_PATHS = {"/api/health", "/api/login", "/api/session"}


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """SEC-1: gate every /api/* call behind PT_API_TOKEN. Empty token (the
    default) disables auth entirely — dev/mock/tests are unaffected. Exempt
    even with a token configured: /api/health (the readiness probe — deploy.sh
    and any uptime monitor must be able to read it before anything is trusted,
    and neither can hold a token; it answers operational state only — lane ages,
    armed flag, provider name, DB error text — on a tailnet-only box) and the Kite
    OAuth redirect endpoints (/api/login, /api/session — the browser hits
    these directly and can't attach a header), plus CORS preflight (OPTIONS)
    and anything outside /api.

    H3: this is also where the request's `Principal` is resolved — once per
    request, at the boundary, rather than per-route. `resolve_http_principal`
    returns None for exactly one condition (a credential was presented and
    REFUSED), which is what the 401 below tests; with auth disabled it returns
    the explicit anonymous-owner principal, never None.

    `request.state.principal` can still be None on an EXEMPT path carrying a bad
    token — the request is served (that is what exempt means) but no identity was
    established, and saying so beats inventing one. Routes must read the
    principal through `Depends(get_principal)`, which turns that case into a 401
    rather than handing anyone a null.

    Exemptions are matched on the UNVERSIONED path, so /api/v1/health is exempt
    for the same reason /api/health is. Getting this wrong would 401 the deploy
    probe the moment deploy.sh moves to v1."""
    settings = get_settings()
    path = unversioned_path(request.url.path)
    principal = resolve_http_principal(request)
    if (
        settings.api_token
        and path.startswith("/api")
        and path not in _AUTH_EXEMPT_PATHS
        and request.method != "OPTIONS"
    ):
        if principal is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    request.state.principal = principal
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
app.include_router(ledger_routes.router)

# H3: mount the SAME routers a second time under /api/v1 (see app/api/versioning.py
# for why this is a mount-time transform and not 45 edited decorators, and for the
# deprecation path off the unprefixed surface). Strictly additive — the four
# includes above are untouched, so every shipped client and scripts/deploy.sh keep
# hitting the exact routes they hit before. Must come BEFORE the SPA catch-all
# registered at the bottom of this file.
mount_versioned(app, routes.router, backtest_routes.router,
                portfolio_routes.router, ledger_routes.router)


def _probe_db() -> tuple[bool, str]:
    """Cheapest possible round-trip to the ledger DB. The 2026-07-23 outage ended
    in DB-pool collapse while /api/health kept answering 200 — the probe has to
    actually touch the pool to see that."""
    try:
        from sqlalchemy import text

        from app.db.session import SessionLocal
        with SessionLocal() as s:
            s.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:                       # noqa: BLE001 — any failure is a failure
        return False, f"{type(e).__name__}: {e}"[:200]


def _schema_info() -> dict:
    """Which schema revision this database is at, and which one this build expects.

    Reported alongside `build` for the same reason `build` is reported: after the
    2026-07-28 episode, deployment state is answered by measurement, not by prose.
    A commit alone does not tell you whether the database underneath it was
    migrated — `up_to_date: false` says a process is running against a schema it
    did not migrate (a restored older DB, or a boot that skipped init_db).

    Deliberately NOT fatal to the readiness verdict. Making it fatal would change
    deploy behaviour, and this migration is meant to be behaviour-preserving; the
    field exists so the condition is *visible* before anything is built on it.
    Defensive like every other read here — a probe must not 500 on its own bug.
    """
    try:
        from app.db.migrate import schema_state
        from app.db.session import engine
        return schema_state(engine)
    except Exception as e:                       # noqa: BLE001
        return {"current": None, "head": None, "up_to_date": None, "error": str(e)}


def _readiness_payload() -> dict:
    """Measure; `engine.readiness` decides. Every read here is defensive: a probe
    that 500s on its own bug is strictly worse than the stub it replaced."""
    from app.engine import readiness

    settings = get_settings()
    thresholds = readiness.Thresholds(
        risk_stale_seconds=settings.health_risk_stale_seconds,
        signal_stale_seconds=settings.health_signal_stale_seconds,
        startup_grace_seconds=settings.health_startup_grace_seconds,
    )
    db_ok, db_error = _probe_db()
    runner = getattr(app.state, "runner", None)

    if runner is None:
        # Lifespan has not finished (or failed). The process is serving HTTP with
        # no engine behind it — exactly the "up but not working" state the stub
        # could not express.
        return readiness.evaluate(
            uptime_seconds=0.0, db_ok=db_ok, db_error=db_error,
            engine_running=False, lane_ages={}, markets_open=None,
            thresholds=thresholds,
        ) | {"engine": {"present": False}}

    try:
        provider_health = runner.health.as_dict()
        auth_error = any(c.get("auth_error") for c in provider_health.values())
    except Exception:
        provider_health, auth_error = {}, False

    try:
        feed = runner.feed_quality.as_dict()
    except Exception:
        feed = {}

    payload = readiness.evaluate(
        uptime_seconds=runner.uptime_seconds(),
        db_ok=db_ok,
        db_error=db_error,
        engine_running=bool(getattr(runner, "running", False)),
        lane_ages=runner.lane_ages(),
        markets_open=runner.markets_open(),
        provider_auth_error=auth_error,
        feed_anomalies=len(feed),
        thresholds=thresholds,
    )
    payload["provider_feed"] = feed
    # Descriptive context — reported, never part of the verdict. Disarmed is a
    # normal resting state (it is the default on every boot), not an unhealthy one.
    payload["engine"] = {
        "present": True,
        "armed": bool(getattr(runner, "armed", False)),
        "provider": getattr(getattr(runner, "provider", None), "name", "unknown"),
    }
    payload["provider_health"] = provider_health
    return payload


@app.get("/api/health")
def health():
    """Readiness probe. 200 when this process is fit to manage real money, 503
    when it is not — the whole point being that it CAN say no. It answered 200
    through both 2026-07 outages, which is why deploy.sh still checks `GET /`
    separately; that stays true, since a broken SPA mount is invisible from here.

    `ok` and `build` keep their old shape and meaning for existing consumers
    (deploy.sh parses `build.commit`), except that `ok` now tracks the verdict.
    """
    try:
        payload = _readiness_payload()
    except Exception as e:                       # noqa: BLE001
        log.error(f"readiness probe itself failed: {e}")
        payload = {"ready": False, "status": "unready", "failed_checks": ["probe"],
                   "checks": [{"name": "probe", "ok": False, "fatal": True,
                               "detail": f"the readiness probe raised: {e}"}]}
    body = {"ok": payload["ready"], "build": get_build_info(),
            "schema": _schema_info(), **payload}
    return JSONResponse(body, status_code=200 if payload["ready"] else 503)


# /api/health is declared on the app rather than on a router, so the versioning
# transform (which walks routers) cannot see it — mirror it by hand. Same
# function object, so the two paths cannot answer differently.
# The unprefixed path stays permanently: deploy.sh and any uptime monitor point
# at it, and a probe URL is the last thing that should ever churn.
app.add_api_route(f"{VERSION_PREFIX}/health", health, methods=["GET"],
                  name="v1_health")


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
