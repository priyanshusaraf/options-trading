"""The Task 4A ownership contract, written before its implementation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import event
from app.backtest import cache
from app.api.principal import Principal, get_principal
from app.db.models import BacktestResult, BacktestRun, Organization
from app.db.planes import Plane, plane_of
from app.db.session import SessionLocal, init_db
from app.main import app


def test_backtest_cache_lookup_is_owner_scoped():
    """A cache probe must accept the caller identity before it can find evidence."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add(BacktestRun(id=1, owner_id="owner", scope="liquid", intervals="day",
                                capital=1, total=1))
        session.flush()
        session.add(BacktestResult(
            run_id=1, instrument_key="NIFTY", interval="day", params_hash="same",
            last_candle_ts=100, schema_version=cache.SCHEMA_VERSION, error="",
        ))
        session.commit()
        assert cache.find_reusable(
            session, "NIFTY", "day", "same", 100, owner_id="owner-b") is None


def test_backtest_evidence_has_owner_and_is_research_plane():
    for model in (BacktestResult,):
        assert "owner_id" in model.__table__.c
    assert plane_of("backtest_runs") is Plane.USER
    assert plane_of("backtest_results") is Plane.USER


def test_revision_0024_exists_for_owned_backtest_evidence():
    versions = Path(__file__).parents[1] / "migrations" / "versions"
    assert any(path.name.startswith("20260812_0024_") for path in versions.iterdir())


def test_foreign_and_absent_backtest_export_are_identical(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="owner-a", name="A"),
                         Organization(organization_id="owner-b", name="B")])
        session.flush()
        session.add(BacktestRun(id=44, owner_id="owner-a", scope="liquid", intervals="day",
                                capital=1, total=0))
        session.commit()
    from app.api import backtest_routes
    monkeypatch.setattr(backtest_routes, "owner_id_for", lambda principal: principal.id)
    app.dependency_overrides[get_principal] = lambda: Principal(
        id="owner-b", kind="owner", scopes=frozenset({"*"}))
    try:
        client = TestClient(app)
        foreign = client.get("/api/backtest/export?run_id=44")
        absent = client.get("/api/backtest/export?run_id=45")
    finally:
        app.dependency_overrides.clear()
    assert (foreign.status_code, foreign.content, dict(foreign.headers)) == (
        absent.status_code, absent.content, dict(absent.headers))


def _client_for(owner_id: str, monkeypatch) -> TestClient:
    from app.api import backtest_routes
    monkeypatch.setattr(backtest_routes, "owner_id_for", lambda principal: principal.id)
    app.dependency_overrides[get_principal] = lambda: Principal(
        id=owner_id, kind="owner", scopes=frozenset({"*"}))
    return TestClient(app)


def test_status_running_is_derived_from_the_owned_run_not_global_admission(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="owner-a", name="A"),
                         Organization(organization_id="owner-b", name="B")])
        session.flush()
        session.add_all([
            BacktestRun(owner_id="owner-a", status="running", scope="liquid", intervals="day",
                        capital=1, total=1),
            BacktestRun(owner_id="owner-b", status="done", scope="liquid", intervals="day",
                        capital=1, total=1),
        ])
        session.commit()
    client = _client_for("owner-b", monkeypatch)
    try:
        assert client.get("/api/backtest/status").json()["running"] is False
    finally:
        app.dependency_overrides.clear()


def test_runs_uses_one_bounded_aggregate_query(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        for _ in range(20):
            session.add(BacktestRun(owner_id="owner", status="done", scope="liquid",
                                    intervals="day", capital=1, total=0))
        session.commit()
    statements = []
    from app.db.session import engine
    def record(_conn, _cursor, statement, _params, _context, _many):
        if "backtest_runs" in statement.lower():
            statements.append(statement)
    event.listen(engine, "before_cursor_execute", record)
    try:
        response = TestClient(app).get("/api/backtest/runs?limit=10")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert response.status_code == 200 and len(response.json()["runs"]) == 10
    assert len(statements) == 1


def test_results_pagination_reports_total_visible_rows(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        run = BacktestRun(owner_id="owner", status="done", scope="liquid", intervals="day",
                          capital=1, total=5)
        session.add(run); session.flush()
        for index in range(5):
            session.add(BacktestResult(owner_id="owner", run_id=run.id,
                instrument_key=f"I{index}", interval="day", trades=20,
                return_pct=float(index), error=""))
        session.commit()
        run_id = run.id
    data = TestClient(app).get(
        f"/api/backtest/results?run_id={run_id}&limit=2&offset=2&min_trades=1"
    ).json()
    assert data["count"] == 2 and data["total"] == 5
    assert data["offset"] == 2 and data["limit"] == 2
