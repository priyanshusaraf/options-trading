"""The Task 4A ownership contract, written before its implementation."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
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
