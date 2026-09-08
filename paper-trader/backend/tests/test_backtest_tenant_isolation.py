"""The Task 4A ownership contract, written before its implementation."""
from __future__ import annotations

import inspect
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import event
from app.backtest import cache
from app.api.principal import Principal, get_principal
from app.db.models import BacktestResult, BacktestRun, Organization
from app.db.planes import Plane, plane_of
from app.db.session import SessionLocal, init_db
from app.main import app
from app.backtest import repository
from app.backtest import sweep


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
    for model in (BacktestRun, BacktestResult):
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


def test_two_owners_cannot_list_detail_latest_or_read_each_others_distinct_evidence(monkeypatch):
    """All public read shapes resolve the principal's owner before a run lookup."""
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="owner-a", name="A"),
                         Organization(organization_id="owner-b", name="B")])
        session.flush()
        runs = [
            BacktestRun(owner_id="owner-a", status="done", scope="liquid", intervals="day",
                        capital=1, total=1, note="A"),
            BacktestRun(owner_id="owner-b", status="done", scope="liquid", intervals="day",
                        capital=1, total=1, note="B"),
        ]
        session.add_all(runs); session.flush()
        session.add_all([
            BacktestResult(owner_id="owner-a", run_id=runs[0].id, instrument_key="NIFTY",
                           interval="day", strategy_key="trend_impulse_v3", trades=20,
                           return_pct=11, error=""),
            BacktestResult(owner_id="owner-b", run_id=runs[1].id, instrument_key="NIFTY",
                           interval="day", strategy_key="trend_impulse_v3", trades=20,
                           return_pct=22, error=""),
        ])
        session.commit()
        a_run, b_run = runs[0].id, runs[1].id
    assert a_run != b_run
    client = _client_for("owner-a", monkeypatch)
    try:
        listed = client.get("/api/backtest/runs").json()["runs"]
        assert [row["id"] for row in listed] == [a_run]
        assert client.get("/api/backtest/status").json()["run"]["id"] == a_run
        owned = client.get(f"/api/backtest/results?run_id={a_run}&min_trades=1")
        foreign = client.get(f"/api/backtest/results?run_id={b_run}&min_trades=1")
        absent = client.get("/api/backtest/results?run_id=999999&min_trades=1")
        assert owned.status_code == 200 and owned.json()["results"][0]["return_pct"] == 11
        assert (foreign.status_code, foreign.content, dict(foreign.headers)) == (
            absent.status_code, absent.content, dict(absent.headers))
        detail = client.get(f"/api/backtest/result/NIFTY/day?run_id={a_run}")
        foreign_detail = client.get(f"/api/backtest/result/NIFTY/day?run_id={b_run}")
        absent_detail = client.get("/api/backtest/result/NIFTY/day?run_id=999999")
        assert detail.status_code == 200 and detail.json()["return_pct"] == 11
        assert (foreign_detail.status_code, foreign_detail.content, dict(foreign_detail.headers)) == (
            absent_detail.status_code, absent_detail.content, dict(absent_detail.headers))
        foreign_export = client.get(f"/api/backtest/export?run_id={b_run}")
        absent_export = client.get("/api/backtest/export?run_id=999999")
        assert (foreign_export.status_code, foreign_export.content, dict(foreign_export.headers)) == (
            absent_export.status_code, absent_export.content, dict(absent_export.headers))
    finally:
        app.dependency_overrides.clear()


def test_every_repository_boundary_requires_explicit_keyword_owner_id():
    """A future caller cannot accidentally fall back to the legacy owner."""
    boundaries = (
        repository.create_run, repository.get_run, repository.latest_run,
        repository.list_runs_with_counts, repository.list_results, repository.result_count,
        repository.result_detail, repository.filtered_results, repository.filtered_counts,
        repository.iter_successful_results, repository.append_result_batch,
        repository.durable_result_count, repository.update_run,
        repository.snapshot_claimable_runs,
    )
    for boundary in boundaries:
        owner = inspect.signature(boundary).parameters["owner_id"]
        assert owner.kind is inspect.Parameter.KEYWORD_ONLY
        assert owner.default is inspect.Parameter.empty

    # The closed reclaim mutations consume an immutable owner-bearing snapshot
    # instead of accepting a fresh owner selector.
    for boundary in (repository.reconcile_frozen_run, repository.claim_frozen_run):
        frozen = inspect.signature(boundary).parameters["frozen"]
        assert frozen.kind is inspect.Parameter.KEYWORD_ONLY

    for boundary in (sweep.start_sweep, sweep._run, sweep._one, sweep._reusable_values,
                     sweep._durable_result_count, sweep._commit_batch,
                     sweep.dispatch_reclaimable):
        owner = inspect.signature(boundary).parameters["owner_id"]
        assert owner.kind is inspect.Parameter.KEYWORD_ONLY
        assert owner.default is inspect.Parameter.empty


def test_poisoned_foreign_cache_probe_has_owner_predicate_and_never_materializes_a_row():
    init_db(reset=True)
    with SessionLocal() as session:
        session.add_all([Organization(organization_id="owner-a", name="A"),
                         Organization(organization_id="owner-b", name="B")])
        session.flush()
        run = BacktestRun(owner_id="owner-a", status="done", scope="liquid", intervals="day",
                          capital=1, total=1)
        session.add(run); session.flush()
        session.add(BacktestResult(owner_id="owner-a", run_id=run.id, instrument_key="NIFTY",
                                   interval="day", params_hash="same", last_candle_ts=100,
                                   schema_version=cache.SCHEMA_VERSION, error="", trades=1))
        session.commit()
        statements = []
        from app.db.session import engine
        def capture(_conn, _cursor, statement, params, _context, _many):
            if "from backtest_results" in statement.lower():
                statements.append((statement.lower(), params))
        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert cache.find_reusable(session, "NIFTY", "day", "same", 100,
                                       owner_id="owner-b") is None
        finally:
            event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    sql, params = statements[0]
    assert "owner_id" in sql and "owner-b" in tuple(params)


def test_export_streams_fixed_size_result_batches_instead_of_loading_a_whole_run(monkeypatch):
    init_db(reset=True)
    with SessionLocal() as session:
        run = BacktestRun(owner_id="owner", status="done", scope="liquid", intervals="day",
                          capital=1, total=501)
        session.add(run); session.flush()
        session.add_all([
            BacktestResult(owner_id="owner", run_id=run.id, instrument_key=f"I{index}",
                           interval="day", trades=1, error="")
            for index in range(501)
        ])
        session.commit()
        run_id = run.id
    from app.db.session import engine
    result_queries = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        if "from backtest_results" in statement.lower():
            result_queries.append(statement.lower())
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = TestClient(app).get(f"/api/backtest/export?run_id={run_id}")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    # 250 + 250 + 1 plus the empty termination probe. Each SELECT remains
    # bounded by the repository's explicit LIMIT rather than row-count size.
    assert len(result_queries) == 4
    assert all("limit" in query and "owner_id" in query for query in result_queries)
