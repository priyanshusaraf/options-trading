"""
FastAPI entrypoint. On startup it initialises the DB, wires the log bus and
engine-state callback into the WebSocket hub, and launches the autonomous engine
loop as a background task. The owner just runs this and watches.

    uvicorn app.main:app --reload        # from the backend/ directory
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette._utils import get_route_path

from app.api import (
    auth_session_routes,
    backtest_routes,
    catalogue_routes,
    connection_routes,
    data_connection_routes,
    ir_experiment_routes,
    ir_edit_routes,
    ir_v2_edit_routes,
    ir_preset_routes,
    research_settings_routes,
    ir_layout_routes,
    ir_routes,
    portfolio_routes,
    product_object_routes,
    research_operation_routes,
    research_review_routes,
    research_spine_routes,
    release_profile_routes,
    routes,
)
from app.account_commerce.publication import build_published_account_commerce_router
from app.monitoring.publication import build_published_monitoring_router
from app.api.principal import (action_for_request, auth_enabled, install_websocket_payload_redaction,
                               is_request_allowed, resolve_http_principal)
from app.api.versioning import VERSION_PREFIX, mount_versioned, unversioned_path
from app.api.csv_request_limits import CsvRequestBodyLimitMiddleware
from research.data.user_csv_import import MAX_CSV_BYTES
from app.core.instruments import get_instrument
from app.core.config import assert_boot_config, get_settings
from app.core.logging import log
from app.core.release_profile import (
    ReleaseServiceRole,
    denied_route,
    is_v0_profile,
    manifest,
    parse_release_service_role,
    refusal_payload,
    required_readiness_planes,
)
from app.core.version import get_build_info, log_build_banner
from app.db.session import init_db
from app.ledger import routes as ledger_routes
from app.ws.manager import manager

# Must exist before Uvicorn starts accepting WebSocket handshakes.  The first
# post-accept application frame carries a bearer, and websockets DEBUG would
# otherwise format raw frame text into the protocol log.
install_websocket_payload_redaction()


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
    release_role = (
        parse_release_service_role(settings.release_service_role)
        if is_v0_profile(settings.release_profile) else None
    )
    app.state.release_service_role = release_role.value if release_role else None
    from app.db.engine import database_url
    from app.ledger.config import ledger_database_url
    from research.config import research_database_url
    from research.guards import (assert_distinct_database_authorities,
                                 assert_pairwise_database_authorities)

    execution_authority = database_url(settings)
    ledger_authority = ledger_database_url(
        database_url=settings.ledger_database_url,
        production=settings.production,
        db_path=settings.ledger_db_path,
    )
    if settings.research_enabled:
        research_authority = research_database_url(
            database_url=settings.research_database_url,
            production=settings.production,
            db_path=settings.research_db_path,
        )
        assert_pairwise_database_authorities(
            execution_authority, research_authority, ledger_authority,
        )
    else:
        assert_distinct_database_authorities(execution_authority, ledger_authority)
    from app.ledger.db import get_sessionmaker as ledger_sessionmaker

    ledger_sessionmaker(ledger_authority)
    if settings.research_enabled:
        from research.domain.base import init_research_db, make_engine as make_research_engine

        research_engine = make_research_engine(research_authority)
        try:
            init_research_db(research_engine)
        finally:
            research_engine.dispose()
    # C7: refuse to start a second backend against the same persistent (non-mock) DB
    # — two instances would trade the same real account with independent in-flight
    # state. Mock (tests, dry-run) skips this so multiple TestClients can coexist.
    from app.db.session import engine as execution_engine
    if settings.provider != "mock" and execution_engine.dialect.name == "sqlite":
        from app.core.instance_lock import acquire_db_lock
        app.state.db_lock = acquire_db_lock(settings.db_path)
    # The validated browser-auth V0 API has no simulation execution cell.
    # Its invited identities/sessions must survive a process restart even when
    # local evidence uses the mock provider. Preserve standard mock reset behavior.
    init_db(reset=settings.provider == "mock" and not settings.browser_auth_enabled)
    manager.bind(asyncio.get_running_loop())

    # Every replica consumes the execution projection outbox. LISTEN only wakes
    # PostgreSQL replicas early; the managed service always polls the durable cursor.
    from app.db.session import SessionLocal
    from app.events.delivery import (CacheInvalidator, DurableReplicaGateway,
                                     ManagedOutboxDelivery, OutboxDispatcher,
                                     ResumeCursorCodec)
    from app.events.outbox import PrincipalScope
    from app.events.planes import execution_outbox, ledger_outbox, research_outbox
    from app.events.projections import reload_durable_projection

    def reload_projection(scope: PrincipalScope, projection: str) -> dict:
        return reload_durable_projection(
            scope, projection, execution_sessionmaker=SessionLocal,
            research_sessionmaker=(research_sm if settings.research_enabled else None),
            ledger_sessionmaker=ledger_sm,
        )

    app.state.event_cache_invalidator = CacheInvalidator()
    event_gateway = DurableReplicaGateway(
        manager, reload_projection=reload_projection,
        cache_invalidator=app.state.event_cache_invalidator)
    replica_boot = uuid.uuid4().hex
    app.state.event_cursor_codec = ResumeCursorCodec(hashlib.sha256(
        (settings.event_cursor_secret or "strategy-os-development-resume-cursor").encode()
    ).digest())
    deliveries = [ManagedOutboxDelivery(
        OutboxDispatcher(
            SessionLocal, execution_outbox(),
            consumer_id=f"api-{socket.gethostname()}-{replica_boot}",
            lease_owner=replica_boot, effect=event_gateway.apply,
        ), engine=execution_engine, plane="execution")]

    ledger_sm = ledger_sessionmaker(ledger_authority)
    ledger_engine = ledger_sm.kw.get("bind")
    deliveries.append(ManagedOutboxDelivery(
        OutboxDispatcher(
            ledger_sm, ledger_outbox(),
            consumer_id=f"ledger-{socket.gethostname()}-{replica_boot}",
            lease_owner=replica_boot, effect=event_gateway.apply,
        ), engine=ledger_engine, plane="ledger"))
    if settings.research_enabled:
        from research.domain.base import make_engine as make_research_engine, make_sessionmaker
        research_delivery_engine = make_research_engine(research_authority)
        research_sm = make_sessionmaker(research_delivery_engine)
        deliveries.append(ManagedOutboxDelivery(
            OutboxDispatcher(
                research_sm, research_outbox(),
                consumer_id=f"research-{socket.gethostname()}-{replica_boot}",
                lease_owner=replica_boot, effect=event_gateway.apply,
            ), engine=research_delivery_engine, plane="research"))
    if is_v0_profile(settings.release_profile):
        app.state.v0_plane_sessionmakers = {
            "execution": SessionLocal,
            "ledger": ledger_sm,
            "research": research_sm,
        }
    delivery_tasks = [asyncio.create_task(delivery.run()) for delivery in deliveries]

    async def stop_deliveries() -> None:
        for delivery in deliveries:
            await delivery.stop()
        for task in delivery_tasks:
            task.cancel()
        await asyncio.gather(*delivery_tasks, return_exceptions=True)
        if settings.research_enabled:
            research_delivery_engine.dispose()
    # Backtest workers are intentionally replaceable. Reclaim only expired/pending
    # durable claims; a non-expired remote lease is never inferred dead.
    if settings.provider == "kite":
        from app.engine.broker_factory import live_execution_enabled
        if live_execution_enabled():
            log.warn("🔴 LIVE MODE — real Kite orders are ENABLED (still gated by ARM; "
                     "disarmed on every start). Use the KILL switch to square off.")
        else:
            log.info("SAFETY: order placement DISABLED — paper trades only, no real capital")
    # Reconstruct any deployed generated strategies from the DB and register them BEFORE
    # the runner loads per-instrument config, so a gen_* watchlist assignment resolves to
    # the real strategy instead of halting as unresolvable. Execution hydration is not a
    # research operation: deployed assignments must keep resolving when the research UI
    # is disabled, and corrupt current rows must evict stale executable bytes.
    from app.db.models import LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID, BacktestRun
    try:
        from app.core.generated_strategies import register_all
        from app.db.session import SessionLocal
        from sqlalchemy import select
        with SessionLocal() as s:
            # Backtest restart dispatch may need any tenant's generated artifact.
            # Hydrate all execution-plane owners before dispatcher claims work.
            # Bound startup work to owners with durable work to reconstruct;
            # loading every tenant partition into one process is neither needed
            # nor safe at scale. Live runners hydrate their own owner separately.
            owners = set(s.scalars(select(BacktestRun.owner_id).where(
                BacktestRun.status.in_(("pending", "running"))).distinct()))
            owners.add(LEGACY_OWNER_ID)
            for owner_id in sorted(owners):
                register_all(s, owner_id=owner_id)
    except Exception as e:
        log.error(f"generated-strategy registration failed at startup: {e}")
    dispatch_research_jobs = (
        not is_v0_profile(settings.release_profile)
        or release_role in {ReleaseServiceRole.RESEARCH_WORKER, ReleaseServiceRole.SCHEDULER}
    )
    if dispatch_research_jobs:
        try:
            from app.backtest.reclaim_authority import ReclaimAuthorityContext
            from app.backtest.sweep import dispatch_all_reclaimable
            authority_context = None
            if settings.research_enabled:
                from app.ir.library import REGISTRY
                authority_context = ReclaimAuthorityContext(
                    registry=REGISTRY, research_sessionmaker=research_sm)
            dispatch_all_reclaimable(authority_context=authority_context)
        except Exception as e:
            log.error(f"backtest restart dispatch failed: {e}")
    if not settings.research_enabled:
        log.info("research plane disabled (PT_RESEARCH_ENABLED=0) — portfolio/research "
                 "API is gated off; deployed execution artifacts remain hydrated")

    worker_role = settings.execution_worker.strip().lower()
    hosts_execution = worker_role == "worker"
    if worker_role == "auto":
        # Local SQLite retains the single-node compatibility cell. Shared PostgreSQL
        # replicas are API-only until explicitly assigned an account worker role.
        hosts_execution = execution_engine.dialect.name == "sqlite"
    if is_v0_profile(settings.release_profile):
        # Boot validation already requires the API-only role. Keep this second,
        # local refusal at the construction boundary so a later role refactor
        # still cannot build a broker runner or claim an execution lease in V0.
        hosts_execution = False
    if not hosts_execution:
        app.state.runner = None
        if is_v0_profile(settings.release_profile):
            log.info("V0 research/signal API ready — execution authority unavailable; no broker cell")
        else:
            log.info("API-only replica ready — durable execution status/control enabled; no broker cell")
        try:
            yield
        finally:
            await stop_deliveries()
        return

    assigned_owner = settings.execution_owner_id.strip()
    assigned_account = settings.execution_broker_account_id.strip()
    if execution_engine.dialect.name == "sqlite":
        assigned_owner = assigned_owner or LEGACY_OWNER_ID
        assigned_account = assigned_account or LEGACY_BROKER_ACCOUNT_ID
    if not assigned_owner or not assigned_account:
        raise RuntimeError(
            "execution worker requires PT_EXECUTION_OWNER_ID and "
            "PT_EXECUTION_BROKER_ACCOUNT_ID")
    from app.execution.leases import LeaseRepository
    lease_repository = LeaseRepository(SessionLocal)
    worker_id = uuid.uuid4().hex
    cell_id = settings.execution_cell_id.strip() or "legacy-cell"
    if settings.restore_safety_state.strip().lower() == "verified":
        from app.execution.disaster_recovery import claim_restored_execution_lease
        lease_token = claim_restored_execution_lease(
            lease_repository, owner_id=assigned_owner,
            broker_account_id=assigned_account, cell_id=cell_id,
            worker_id=worker_id,
            verification_address=settings.restore_verification_address.strip(),
            old_primary_isolated=settings.restore_old_primary_isolated)
    else:
        lease_token = lease_repository.claim(
            owner_id=assigned_owner, broker_account_id=assigned_account,
            cell_id=cell_id, worker_id=worker_id,
            host_diagnostic=socket.gethostname())
    from app.engine.runner import EngineRunner
    runner = EngineRunner(owner_id=assigned_owner,
                          broker_account_id=assigned_account,
                          execution_lease_token=lease_token)  # factory logs chosen provider
    from app.core.deployments import disarm_all
    with SessionLocal() as disarm_session:
        lease_repository.bind_money_session(disarm_session, lease_token)
        disarm_all(disarm_session, owner_id=assigned_owner,
                   broker_account_id=assigned_account)
        disarm_session.commit()
    app.state.runner = runner

    async def on_update(state: dict) -> None:
        await manager.broadcast((runner.owner_id, runner.broker_account_id),
                                {"type": "state", "data": state})

    async def on_position_ticks(ticks: dict) -> None:
        await manager.broadcast((runner.owner_id, runner.broker_account_id),
                                {"type": "position_ticks", "data": ticks})

    runner.on_update = on_update
    runner.on_position_ticks = on_position_ticks
    # Process-global LogBus entries lack tenant scope. Keep them on the
    # privileged operator surface until producers can supply one.

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
        reconcile = getattr(runner.broker, "reconcile_execution_lease", None)
        if reconcile is None:
            await asyncio.to_thread(runner.broker.recover_journal, runner.provider.now())
            evidence = "paper/local journal replay completed"
        else:
            evidence = await asyncio.to_thread(reconcile, runner.provider.now())
        lease_repository.activate(
            lease_token, reconciliation_evidence=evidence[:200])
    except Exception as e:
        log.error(f"order journal recovery failed at startup: {e}")
        lease_repository.block(lease_token, f"startup reconciliation failed: {type(e).__name__}")
        runner.stop()
        try:
            runner.broker.close()
        finally:
            raise RuntimeError("execution recovery failed; runner loops were not started") from e

    async def lease_watchdog() -> None:
        while runner.running:
            await asyncio.sleep(10)
            try:
                await asyncio.to_thread(lease_repository.heartbeat, lease_token)
            except Exception as exc:
                log.error(f"execution lease heartbeat lost: {exc}", event="LEASE_LOST")
                runner.stop()
                return

    async def control_loop() -> None:
        while runner.running:
            await asyncio.sleep(0.5)
            try:
                commands = await asyncio.to_thread(
                    lease_repository.claim_controls, lease_token, limit=8)
                for command in commands:
                    try:
                        from app.execution.controls import apply_control
                        async with runner._lock:
                            await asyncio.to_thread(
                                apply_control, lease_repository, lease_token, runner,
                                command, SessionLocal)
                    except Exception:
                        continue
            except Exception as exc:
                log.error(f"execution control loop failed: {exc}", event="CONTROL_LOOP_FAIL")

    control_task = asyncio.create_task(control_loop())

    lease_task = asyncio.create_task(lease_watchdog())
    signal_task = asyncio.create_task(runner.run_signal_loop())
    risk_task = asyncio.create_task(runner.run_risk_loop())
    # Journal: detect trades the OWNER placed by hand on the Kite account and
    # file them for reasoning. A third lane on purpose — it reads the orderbook
    # and writes only to ledger.db, never to positions/trades, and it never
    # takes runner._lock (see the 2026-07-13 risk_loop_stalled incident). If it
    # dies, trading is entirely unaffected.
    from app.db.session import SessionLocal
    from app.ledger.lane import run_manual_detect_loop
    detect_task = asyncio.create_task(run_manual_detect_loop(
        runner.provider, SessionLocal, ledger_sessionmaker(ledger_authority),
        get_settings(), runner.provider.now, owner_id=runner.owner_id,
        broker_account_id=runner.broker_account_id))
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        signal_task.cancel()
        risk_task.cancel()
        detect_task.cancel()
        # Cancellation of asyncio.to_thread does not stop its worker.  Each lane
        # drains its current worker before propagating cancellation; wait for that
        # contract before closing the shared session.  Otherwise a quick TestClient
        # restart can reach init_db(reset=True) while the old worker still owns a
        # SQLite transaction, and production shutdown can close a broker session
        # while an order poll is still using it.
        lease_task.cancel()
        control_task.cancel()
        await asyncio.gather(signal_task, risk_task, detect_task, lease_task, control_task,
                             return_exceptions=True)
        # Best-effort — a failure here must not stop the process exiting.
        try:
            runner.broker.close()
        except Exception as e:
            log.warn(f"broker session close failed at shutdown: {e}")
        try:
            lease_repository.release(lease_token)
        except Exception as e:
            log.warn(f"execution lease release failed at shutdown: {e}")
        await stop_deliveries()


class _PollingRouteFilter(logging.Filter):
    """Demote high-frequency UI polling GETs out of the access log (2026-07-15
    autopsy: ~34% of the 3-day journal was polling noise). Real mutating/rare
    routes still log normally."""
    _NOISY = ("/api/execution/state", "/api/status", "/api/signals")
    # Both surfaces, or the filter silently stops working the day the SPA moves
    # to /api/v1 and the access log fills up again for no visible reason.
    _NOISY_PATHS = tuple(_NOISY) + tuple(
        f"{VERSION_PREFIX}{p[len('/api'):]}" for p in _NOISY)
    _SENSITIVE_CALLBACKS = (
        "/api/oauth/callback",
        "/api/v1/data-connections/oauth/callback",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not (
            any(f"GET {p} " in msg for p in self._NOISY_PATHS)
            or any(f"GET {p}" in msg for p in self._SENSITIVE_CALLBACKS)
        )


logging.getLogger("uvicorn.access").addFilter(_PollingRouteFilter())

app = FastAPI(title="Options Paper Trader", lifespan=lifespan)
app.add_middleware(CsvRequestBodyLimitMiddleware, max_file_bytes=MAX_CSV_BYTES)


@app.exception_handler(ir_experiment_routes.GraphExperimentFailure)
async def graph_experiment_failure_handler(
    _request: Request, exc: ir_experiment_routes.GraphExperimentFailure
):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


# Request-controlled dictionary keys, union tags and validator messages can all
# occur in Pydantic errors. Only this fixed vocabulary may cross the V0 boundary.
# Unknown fields remain actionable as a generic location, without publishing
# strategy names, graph keys or future validators' exception text.
_V0_VALIDATION_FIELDS = frozenset("""
    body path query header cookie name description identifier graph document
    project_id graph_identifier version format_version base_revision
    base_presentation_revision edits presentation_edits operation display_name
    instance_id parameter value overrides domain secret_params node_index
    source target socket edge_index x y width height group_id frame
    program_name hypothesis_statement datasets instrument_key interval days seed
    gates min_oos_trades n_folds min_positive_fold_fraction optimize_search
    pbo_threshold sibling_trials cost_assumptions capital slippage_bps
    slippage_multiplier charge_model sizing_model left right left_run_id
    right_run_id run_id graph_version expected_status decision reason status
    credential bundle provider connection_id
""".split())
_V0_VALIDATION_MESSAGES = {
    "missing": "Field required",
    "extra_forbidden": "Unexpected field",
    "string_type": "Expected a string",
    "string_too_short": "String is too short",
    "string_too_long": "String is too long",
    "int_type": "Expected an integer",
    "int_parsing": "Expected an integer",
    "float_type": "Expected a number",
    "float_parsing": "Expected a number",
    "bool_type": "Expected a boolean",
    "bool_parsing": "Expected a boolean",
    "dict_type": "Expected an object",
    "list_type": "Expected a list",
    "greater_than": "Value is below the allowed range",
    "greater_than_equal": "Value is below the allowed range",
    "less_than": "Value is above the allowed range",
    "less_than_equal": "Value is above the allowed range",
    "too_short": "Too few items",
    "too_long": "Too many items",
    "literal_error": "Unsupported value",
    "union_tag_invalid": "Unsupported variant",
    "union_tag_not_found": "Variant is required",
    "json_invalid": "Invalid JSON",
    "finite_number": "Expected a finite number",
    "value_error": "Invalid value",
}


def _v0_validation_errors(errors: list[dict]) -> list[dict]:
    closed = []
    for error in errors[:32]:
        kind = error.get("type")
        if kind not in _V0_VALIDATION_MESSAGES:
            kind = "value_error"
        location = [
            part if (type(part) is int and part >= 0) or (
                isinstance(part, str) and part in _V0_VALIDATION_FIELDS
            ) else "field"
            for part in error.get("loc", ())[:12]
        ]
        closed.append({"loc": location, "type": kind,
                       "msg": _V0_VALIDATION_MESSAGES[kind]})
    return closed


@app.exception_handler(RequestValidationError)
async def editor_request_validation_handler(
    request: Request, exc: RequestValidationError
):
    """Preserve editor envelopes; close diagnostic values throughout V0.

    Standard routes retain their established validation body. The versioned
    mirror is normalized through ``unversioned_path`` before matching.
    """
    path = unversioned_path(request.url.path)
    v0 = is_v0_profile(get_settings().release_profile)
    errors = _v0_validation_errors(exc.errors()) if v0 else exc.errors()
    if (
        path.startswith("/api/ir/projects/")
        and (
            ("/graphs/" in path and path.endswith("/experiments"))
            or path.endswith("/experiments/comparisons")
            or path.endswith("/version-comparisons")
            or path.endswith("/decisions")
            or path.endswith("/findings")
            or path.endswith("/revisions")
        )
    ):
        return JSONResponse(
            status_code=422,
            content=ir_experiment_routes.request_validation_envelope(errors),
        )
    if (
        path.startswith("/api/ir/projects/")
        and "/graphs/" in path
        and path.endswith("/edits")
    ):
        return JSONResponse(
            status_code=422,
            content=ir_edit_routes.request_validation_envelope(errors),
        )
    if v0:
        return JSONResponse(status_code=422, content={
            "code": "REQUEST_VALIDATION_FAILED",
            "message": "Request validation failed",
            "detail": errors,
        })
    if path.startswith("/api/connections/") and path.endswith("/credential"):
        # FastAPI's default envelope includes pydantic's `input` — the value that failed
        # validation. On every other route that is a helpful echo; on this one it is a live
        # broker access token sent back in an error body, which lands in browser network logs,
        # proxy error logs and any client-side error reporter. `connection_routes` is careful
        # never to interpolate the bundle into its own messages, and until this branch existed
        # the framework undid that one layer down. Found by an independent security review,
        # 2026-08-11.
        #
        # `loc` and `msg` are kept: the caller still learns WHICH field was wrong and why, which
        # is the whole job of a 422. Only the value is dropped.
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {"detail": [{k: v for k, v in err.items() if k != "input"}
                            for err in exc.errors()]}),
        )
    return await request_validation_exception_handler(request, exc)

_AUTH_EXEMPT_PATHS = {
    "/api/health", "/api/oauth/callback",
    "/api/data-connections/oauth/callback", "/api/release-profile",
}
_V0_ROLE_EXEMPT_PATHS = {"/api/health", "/api/readiness", "/api/release-profile"}


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
    # Share the router's decoded path and mount semantics. Reconstructing a URL
    # would mistake encoded path question/hash characters for URL delimiters.
    path = unversioned_path(get_route_path(request.scope))
    browser_route = False
    browser_public = False
    stale_browser_cookie = False
    if settings.browser_auth_enabled:
        from app.accounts import browser_auth
        if not browser_auth.validate_configuration(settings):
            return auth_session_routes.refusal(503)
        browser_route = (request.method, path) in auth_session_routes.AUTH_ROUTES
        browser_public = (request.method, path) in auth_session_routes.PUBLIC_ROUTES
    try:
        if settings.browser_auth_enabled:
            from starlette.concurrency import run_in_threadpool
            principal = await run_in_threadpool(resolve_http_principal, request)
        else:
            principal = resolve_http_principal(request)
    except Exception as exc:
        from app.accounts.browser_auth import AuthRefusal, SessionRefusal
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(exc, SessionRefusal) and (path in _AUTH_EXEMPT_PATHS or not path.startswith('/api')):
            principal = None
            stale_browser_cookie = True
        elif isinstance(exc, AuthRefusal):
            return auth_session_routes.refusal(exc.status)
        elif settings.browser_auth_enabled and isinstance(exc, SQLAlchemyError):
            return auth_session_routes.refusal(503)
        else:
            raise
    if (
        auth_enabled()
        and path.startswith("/api")
        and path not in _AUTH_EXEMPT_PATHS
        and not browser_public
        and request.method != "OPTIONS"
    ):
        if principal is None:
            if settings.browser_auth_enabled:
                return auth_session_routes.refusal(401)
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    request.state.principal = principal
    unavailable = denied_route(settings.release_profile, request.method, path)
    if unavailable is not None:
        return JSONResponse(refusal_payload(unavailable), status_code=409)
    if (
        is_v0_profile(settings.release_profile)
        and parse_release_service_role(settings.release_service_role) is not ReleaseServiceRole.API
        and path.startswith("/api")
        and path not in _V0_ROLE_EXEMPT_PATHS
    ):
        return JSONResponse({
            "code": "V0_SERVICE_ROLE_UNAVAILABLE",
            "release_profile": settings.release_profile,
            "service_role": settings.release_service_role,
            "message": "this V0 service role does not serve product API routes",
        }, status_code=503)
    action = action_for_request(request.method, path)
    # A durable user may only reach a resource family whose authorization and
    # organization-scoped repository boundary have both been named.  Legacy
    # runner endpoints remain callable only through the compatibility owner
    # until Task 5C converts their process-global state.
    if (action is None and not browser_route and path not in _AUTH_EXEMPT_PATHS and principal is not None
            and principal.kind == "user" and path.startswith("/api")):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if action is not None and not is_request_allowed(principal, action):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    response = await call_next(request)
    if stale_browser_cookie:
        auth_session_routes.clear_cookie(response)
    return response


@app.middleware("http")
async def data_connection_cache_gate(request: Request, call_next):
    """Never cache direct data-connection status, errors or callback responses."""
    response = await call_next(request)
    path = unversioned_path(get_route_path(request.scope))
    if path == "/api/data-connections" or path.startswith("/api/data-connections/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def market_context_cache_gate(request: Request, call_next):
    """Keep private research charts and monitoring records out of browser/shared caches."""
    response = await call_next(request)
    path = unversioned_path(get_route_path(request.scope))
    if path.startswith("/api/monitoring/") or (path.startswith("/api/ir/projects/") and "/market-context" in path):
        response.headers["Cache-Control"] = "no-store"
    return response


# CORSMiddleware is registered AFTER auth_gate above so it ends up OUTERMOST
# (Starlette wraps middleware in reverse-of-registration order): a 401 minted
# by auth_gate still passes back out through CORS and gets its headers
# attached, and a preflight OPTIONS is answered by CORS before it ever
# reaches auth_gate.
app.add_middleware(
    CORSMiddleware, allow_origins=([get_settings().browser_auth_origin] if get_settings().browser_auth_enabled
                                  else get_settings().cors_origins_list), allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes.router)
app.include_router(backtest_routes.router)
app.include_router(portfolio_routes.router)
app.include_router(ledger_routes.router)
app.include_router(ir_routes.router)
app.include_router(ir_layout_routes.router)
app.include_router(product_object_routes.router)
app.include_router(ir_edit_routes.router)
app.include_router(ir_v2_edit_routes.router)
app.include_router(ir_preset_routes.router)
app.include_router(research_settings_routes.router)
app.include_router(build_published_monitoring_router())
app.include_router(ir_experiment_routes.router)
app.include_router(catalogue_routes.router)
app.include_router(research_operation_routes.router)
app.include_router(research_review_routes.router)
app.include_router(research_spine_routes.router)
app.include_router(connection_routes.router)
app.include_router(data_connection_routes.router)
app.include_router(release_profile_routes.router)
app.include_router(auth_session_routes.router)
published_account_commerce_router = build_published_account_commerce_router()
app.include_router(published_account_commerce_router)

# H3: mount the SAME routers a second time under /api/v1 (see app/api/versioning.py
# for why this is a mount-time transform and not 45 edited decorators, and for the
# deprecation path off the unprefixed surface). Strictly additive — the four
# includes above are untouched, so every shipped client and scripts/deploy.sh keep
# hitting the exact routes they hit before. Must come BEFORE the SPA catch-all
# registered at the bottom of this file.
mount_versioned(app, routes.router, backtest_routes.router,
                portfolio_routes.router, ledger_routes.router, ir_routes.router,
                ir_layout_routes.router, product_object_routes.router,
                ir_edit_routes.router, ir_experiment_routes.router, catalogue_routes.router,
                ir_v2_edit_routes.router, ir_preset_routes.router, research_settings_routes.router,
                research_operation_routes.router, research_review_routes.router,
                research_spine_routes.router,
                connection_routes.router, release_profile_routes.router, auth_session_routes.router)


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


def _probe_sessionmaker(sessionmaker) -> tuple[bool, str]:
    try:
        from sqlalchemy import text
        with sessionmaker() as session:
            session.execute(text("SELECT 1"))
        return True, ""
    except Exception as exc:                      # noqa: BLE001
        if is_v0_profile(get_settings().release_profile):
            return False, "DATABASE_PROBE_FAILED"
        return False, f"{type(exc).__name__}: {exc}"[:200]


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
        error = "SCHEMA_PROBE_FAILED" if is_v0_profile(get_settings().release_profile) else str(e)
        return {"current": None, "head": None, "up_to_date": None, "error": error}


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
    if is_v0_profile(settings.release_profile):
        role = parse_release_service_role(settings.release_service_role)
        sessionmakers = getattr(app.state, "v0_plane_sessionmakers", {})
        planes = {}
        for plane in required_readiness_planes(role):
            factory = sessionmakers.get(plane)
            ok, error = ((False, "DATABASE_SESSION_UNAVAILABLE") if factory is None
                         else _probe_sessionmaker(factory))
            planes[plane] = {"ok": ok, "error": error}
        failed = [f"database:{plane}" for plane, state in planes.items() if not state["ok"]]
        ready = not failed
        return {
            "ready": ready,
            "status": "ok" if ready else "unready",
            "failed_checks": failed,
            "database_planes": planes,
            "engine": {"present": False},
            "release_profile": settings.release_profile,
            "service_role": role.value,
            "execution_authority": False,
        }

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
        "book": getattr(runner, "book", None),
        # Open positions belonging to the OTHER execution book. Descriptive, never part
        # of the verdict: this process cannot close them, so failing the probe would take
        # down the book it *can* manage without helping the one it can't. Reported so the
        # orphan L1.3B makes possible is visible rather than silent (ADR 0012 §6.4).
        "foreign_book_positions": _foreign_book_positions(runner),
    }
    payload["provider_health"] = provider_health
    return payload


@app.get("/api/readiness")
def execution_readiness():
    """Full execution-readiness payload: feed quality, lane ages, degraded checks.

    Rehomed off the public `/api/health` when that route became tenant-neutral:
    this payload carries account-specific runner and position state, which must
    not cross an unauthenticated boundary.  The auth middleware protects this
    path (it is not on the exemption list); with `PT_API_TOKEN` empty — local
    development — it answers to the anonymous owner exactly like every other
    authenticated surface.

    Status semantics are the ones this payload always had: 503 when any check
    FAILED (the process must be able to say no), 200 while merely degraded or
    starting.  A probe that raises answers 503 naming itself — a 500 here is
    indistinguishable from a dead process to every monitor.
    """
    try:
        payload = _readiness_payload()
    except Exception:                            # noqa: BLE001 — any failure is a failure
        payload = {"ready": False, "status": "unready",
                   "failed_checks": ["probe"]}
    # Legacy consumer contract carried over from the pre-tenancy /api/health:
    # every answer identifies its build, and `ok` tracks the verdict.
    payload["ok"] = bool(payload.get("ready"))
    payload.setdefault("build", get_build_info())
    return JSONResponse(payload, status_code=200 if payload.get("ready") else 503)


app.add_api_route(f"{VERSION_PREFIX}/readiness", execution_readiness,
                  methods=["GET"], name="v1_readiness")


def _foreign_book_positions(runner) -> list[str]:
    """Never raise: the readiness probe answering is more important than this field."""
    try:
        return runner.report_foreign_book_positions()
    except Exception:
        return []


@app.get("/api/health")
def health():
    """Readiness probe. 200 when this process is fit to manage real money, 503
    when it is not — the whole point being that it CAN say no. It answered 200
    through both 2026-07 outages, which is why deploy.sh still checks `GET /`
    separately; that stays true, since a broken SPA mount is invisible from here.

    `ok` and `build` keep their old shape and meaning for existing consumers
    (deploy.sh parses `build.commit`), except that `ok` now tracks the verdict.
    """
    # Public health is tenant-neutral process liveness. Execution readiness
    # carries account-specific runner and position state and must not cross this
    # unauthenticated boundary.
    db_ok, _ = _probe_db()
    settings = get_settings()
    profile = manifest(
        settings.release_profile,
        research_enabled=settings.research_enabled,
        service_role=settings.release_service_role,
    )
    return JSONResponse({"ok": db_ok, "ready": db_ok,
                         "status": "ok" if db_ok else "unready",
                         "build": get_build_info(),
                         "schema": _schema_info(),
                         "release_profile": profile["release_profile"],
                         "service_role": profile["service_role"],
                         "execution_authority": profile["execution_authority"]},
                        status_code=200 if db_ok else 503)


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
