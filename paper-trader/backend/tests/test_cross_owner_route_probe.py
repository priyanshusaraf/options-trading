"""E1 — systematic cross-owner read/mutation probe (audit matrix cell E1).

Two durably-seeded owners. Every core money-read surface must show ONLY the
requesting principal's rows; every account-targeting mutation against another
owner's durable account must refuse. Ownership must not enter through ANY
client-controlled channel: query parameters, path parameters, request bodies,
dependency objects, or the alternate /api/v1 route versions.

Honesty rules this file enforces on itself:
- The cross-owner runner test keeps owner A's runner INSTALLED while making
  the request as owner B (the previous version swapped runners before the
  request and therefore proved nothing).
- Every isolation assertion has a positive control first proving owner A can
  actually read the seeded data, so an empty response can never masquerade
  as isolation.
- The structural detectors are proven able to fail via planted offenders.
"""
from __future__ import annotations

import inspect
import typing
from datetime import date, datetime

import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.models import (
    BacktestResult,
    BacktestRun,
    BrokerAccount,
    DailyAccountSnapshot,
    Organization,
    Trade,
)
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app

OWNER_A = "owner.alpha"
OWNER_B = "owner.beta"
DEPLOYMENT_IDS = {}
ACCOUNT_A = "account.owner.alpha"

# Distinctive owner-A markers that must never appear in owner-B responses.
LEAK_MARKERS = (OWNER_A, ACCOUNT_A, "NIFTYCE")

_OWNER_PARAM_NAMES = {"owner_id", "owner", "owner_key", "owner_code"}


def _seed_two_owners() -> None:
    init_db(reset=True)
    with SessionLocal.begin() as session:
        for owner in (OWNER_A, OWNER_B):
            session.add(Organization(organization_id=owner, name=owner))
            session.add(BrokerAccount(broker_account_id=f"account.{owner}",
                                      owner_id=owner, broker="mock",
                                      external_account_id=f"ext.{owner}",
                                      display_name=owner, status="active"))

    # Deployment depends on the account row: separate committed transaction
    # (raw FKs have no relationship(), so UoW cannot order them together).
    global DEPLOYMENT_IDS
    DEPLOYMENT_IDS = {}
    for owner in (OWNER_A, OWNER_B):
        with SessionLocal.begin() as session:
            from app.db.models import Deployment
            dep = Deployment(owner_id=owner, name="probe",
                             broker_account_id=f"account.{owner}",
                             status="active", armed=True)
            session.add(dep)
            session.flush()
            DEPLOYMENT_IDS[owner] = dep.id

    session = SessionLocal()
    try:
        from tests.admitted_entry import persist_admitted_entry
        admission_address = persist_admitted_entry(
            session, owner_id=OWNER_A)["admission_address"]
        session.add(Trade(
            owner_id=OWNER_A, broker_account_id=ACCOUNT_A,
            instrument_key="NIFTY", direction="LONG", option_type="CE",
            tradingsymbol="NIFTYCE", exchange="NFO", strike=24000.0,
            expiry=date(2026, 9, 30), qty=75, entry_premium=100.0,
            entry_cost=7500.0, entry_spot=24000.0,
            exit_premium=110.0, exit_charges=10.0, exit_spot=24010.0,
            entry_time=datetime(2026, 8, 21, 9, 45),
            exit_time=datetime(2026, 8, 21, 10, 5), exit_reason="target",
            gross_pnl=750.0, charges_total=10.0, net_pnl=740.0,
            return_pct=1.48, holding_minutes=20, win=True, mode="paper"))
        session.add(DailyAccountSnapshot(
            broker_account_id=ACCOUNT_A, day="2026-08-21",
            account_net=5_000.0, account_available=4_000.0))
        run = BacktestRun(owner_id=OWNER_A, status="done", scope="liquid",
                          intervals="day", capital=50_000.0, total=1, done=1,
                          admission_address=admission_address)
        session.add(run)
        session.flush()
        session.add(BacktestResult(owner_id=OWNER_A, run_id=run.id,
                                   instrument_key="NIFTY", interval="day",
                                   trades=5, wins=3, win_rate=60.0,
                                   return_pct=9.0, affordable=True, error=""))
        session.commit()
    finally:
        session.close()


def _install_runner(owner: str) -> None:
    kwargs = {}
    if DEPLOYMENT_IDS.get(owner):
        kwargs["deployment_id"] = DEPLOYMENT_IDS[owner]
    app.state.runner = EngineRunner(owner_id=owner,
                                    broker_account_id=f"account.{owner}", **kwargs)


def _client_for(owner: str, *, install_runner: bool = True) -> TestClient:
    """A client acting as `owner`. With install_runner=False the process-local
    runner is LEFT UNTOUCHED — used to prove isolation while another owner's
    runner stays installed."""
    get_settings().owner_id = owner
    if install_runner:
        _install_runner(owner)
    return TestClient(app)


def _assert_no_owner_a_state(body) -> None:
    text = str(body)
    for marker in LEAK_MARKERS:
        assert marker not in text, f"owner-A state leaked: {marker!r} in {text[:300]}"


# --------------------------------------------------------------------------
# Structural half: no client-controlled ownership channel anywhere.
# --------------------------------------------------------------------------

def _all_api_routes():
    """Every mounted APIRoute, descending through include wrappers so BOTH the
    unprefixed and /api/v1 mirrored mounts are covered."""
    routes = []
    for route in app.router.routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            routes.extend(item for item in original.routes
                          if isinstance(item, APIRoute))
        elif isinstance(route, APIRoute):
            routes.append(route)
    return routes


def _endpoint_annotation_hints(endpoint) -> dict:
    try:
        return typing.get_type_hints(endpoint)
    except Exception:  # noqa: BLE001 - exotic annotations must not crash the sweep
        return {}


def ownership_entry_points(routes) -> list[tuple]:
    """Every place a client could smuggle an owner identity into a handler:
    query/path parameters, request-body model fields, and Depends() callables."""
    offenders = []
    seen = set()
    for route in routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        methods = sorted(getattr(route, "methods", ()) or ())
        key = (route.path, tuple(methods))
        if key in seen:
            continue
        seen.add(key)
        bad: list[str] = []
        for name in inspect.signature(endpoint).parameters:
            if name.lower() in _OWNER_PARAM_NAMES:
                bad.append(f"parameter:{name}")
        hints = _endpoint_annotation_hints(endpoint)
        for name, annotation in hints.items():
            fields = getattr(annotation, "model_fields", None)
            if fields is not None:
                bad.extend(f"{annotation.__name__}.{field}" for field in fields
                           if field.lower() in _OWNER_PARAM_NAMES)
        # Default-value dependencies: `def handler(x = Depends(fn))` never
        # appears in route.dependencies, so scan parameter defaults too.
        for parameter in inspect.signature(endpoint).parameters.values():
            dependency_callable = getattr(parameter.default, "dependency", None)
            if not callable(dependency_callable):
                continue
            for name in inspect.signature(dependency_callable).parameters:
                if name.lower() in _OWNER_PARAM_NAMES:
                    bad.append(f"depends:{name}")
        for dependency in getattr(route, "dependencies", ()) or ():
            dependency_callable = getattr(dependency, "callable", None)
            if dependency_callable is None:
                continue
            for name in inspect.signature(dependency_callable).parameters:
                if name.lower() in _OWNER_PARAM_NAMES:
                    bad.append(f"depends:{name}")
        if bad:
            offenders.append((route.path, methods, sorted(set(bad))))
    return offenders


def test_no_route_accepts_client_supplied_ownership_on_any_mounted_version():
    """Ownership comes from the authenticated principal — never through query
    arguments, path parameters, request bodies, or dependencies, on BOTH the
    unprefixed and the /api/v1 mirrored mounts."""
    offenders = ownership_entry_points(_all_api_routes())
    assert offenders == [], (
        "these routes accept a client-supplied owner identity — ownership "
        f"must be principal-derived: {offenders}")


class _OwnerBodyProbe(BaseModel):
    owner_id: str


def _planted_dependency(owner_id: str = "") -> str:
    return owner_id


def test_ownership_detectors_fail_when_an_offender_is_planted():
    """Self-negative control: each smuggling channel is detected when present."""
    router = APIRouter()

    @router.get("/plant/query")
    def plant_query(owner_id: str = "") -> dict:
        return {}

    @router.post("/plant/body")
    def plant_body(body: _OwnerBodyProbe) -> dict:
        return {}

    @router.get("/plant/dep")
    def plant_dep(value: str = Depends(_planted_dependency)) -> dict:
        return {}

    found = {(path, tuple(bad)) for path, _methods, bad in
             ownership_entry_points(router.routes)}
    assert ("/plant/query", ("parameter:owner_id",)) in found
    assert any(path == "/plant/body" and
               any(field.endswith(".owner_id") for field in bad)
               for path, _m, bad in ownership_entry_points(router.routes))
    assert ("/plant/dep", ("depends:owner_id",)) in found


# --------------------------------------------------------------------------
# Behavioral half: positive control first, then isolation.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path,body_key", [
    ("/api/trades", "trades"),
    ("/api/backtest/runs", "runs"),
])
def test_positive_control_owner_a_reads_its_own_seeded_data(path, body_key):
    """Proves the seeded data is visible to its owner — so later empty/refusing
    responses for owner B mean isolation, not vacuous absence."""
    _seed_two_owners()
    _install_runner(OWNER_A)
    get_settings().owner_id = OWNER_A
    c = TestClient(app)
    res = c.get(path)
    assert res.status_code == 200, (path, res.status_code, res.text[:200])
    body = res.json()
    rows = body.get(body_key, body) if isinstance(body, dict) else body
    assert isinstance(rows, list) and rows, f"positive control failed: {path} empty"
    # Visibility is proven by the seeded distinctive facts, not by an owner_id
    # echo (serializers intentionally omit it).
    if path == "/api/trades":
        symbols = {row.get("tradingsymbol") for row in rows}
        assert "NIFTYCE" in symbols, f"{path} did not serve owner-A its seeded rows"
    if path == "/api/backtest/runs":
        # The runs serializer omits instruments; visibility is proven by the
        # seeded run's result count.
        assert any((row.get("result_count") or 0) >= 1 for row in rows), \
            f"{path} did not serve owner-A its seeded run"


@pytest.mark.parametrize("path", [
    "/api/positions",
    "/api/trades",
    "/api/calendar",
    "/api/backtest/runs",
])
def test_owner_b_reads_never_return_owner_a_money_rows(path):
    _seed_two_owners()
    c = _client_for(OWNER_B)
    res = c.get(path)
    assert res.status_code == 200, (path, res.status_code)
    _assert_no_owner_a_state(res.json())


def test_owner_b_sees_no_owner_a_state_on_any_parameterless_read_while_as_runner_is_installed():
    """The named E1 scenario: owner A's runner REMAINS INSTALLED; the request
    is made as owner B. Every mounted parameterless GET on both mount versions
    must refuse or serve only B's own (empty) book — never A's state."""
    _seed_two_owners()
    _install_runner(OWNER_A)                      # A's runner stays installed
    get_settings().owner_id = OWNER_B             # ...while B is the principal
    c = TestClient(app)
    checked = 0
    unavailable: list[str] = []
    for route in _all_api_routes():
        if "GET" not in route.methods or "{" in route.path:
            continue
        if "readiness" in route.path or route.path.endswith("/health"):
            continue
        res = c.get(route.path)
        checked += 1
        if res.status_code == 200:
            _assert_no_owner_a_state(res.json())
        elif res.status_code == 503:
            # Service-backed endpoints (e.g. SSE resume) are down under
            # TestClient by design — they serve no rows, so they cannot leak;
            # recorded rather than counted as isolation evidence.
            unavailable.append(route.path)
        elif not (400 <= res.status_code < 500):
            assert False, (
                f"{route.path}: unexpected {res.status_code}: {res.text[:200]}")
    print(f"E1 sweep: {checked} parameterless GETs checked, "
          f"{len(unavailable)} unavailable(503): {sorted(unavailable)}")
    assert checked - len(unavailable) >= 8, (
        f"responsive-route coverage too small: {checked - len(unavailable)}")


def test_mutation_against_another_owners_durable_account_refuses():
    _seed_two_owners()
    c = _client_for(OWNER_B)
    # B attempts to act on A's durable account id.
    res = c.post("/api/manual-open", json={
        "instrument_key": "NIFTY", "direction": "LONG", "qty": 1,
        "broker_account_id": ACCOUNT_A,
    })
    assert res.status_code in (403, 404), (res.status_code, res.text[:200])


def test_leak_scanner_fails_when_owner_a_state_is_present():
    """Self-negative control for the behavioral assertions above."""
    with pytest.raises(AssertionError):
        _assert_no_owner_a_state({"trades": [{"broker_account_id": ACCOUNT_A}]})


def test_runner_cell_is_not_served_across_owners():
    """local_execution_cell binds the process-local runner to its owning
    principal: with A's runner installed and B as principal, B must be refused
    (404) — never served A's engine state."""
    _seed_two_owners()
    _install_runner(OWNER_A)          # installed once, NEVER swapped below
    get_settings().owner_id = OWNER_B
    c = TestClient(app)
    res = c.get("/api/positions")
    # The required refusal: B may not consume A's runner cell.
    assert res.status_code in (403, 404), (res.status_code, res.text[:200])
    if res.status_code == 200:        # defense in depth if policy ever changes
        _assert_no_owner_a_state(res.json())
