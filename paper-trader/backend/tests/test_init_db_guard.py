"""init_db(reset=True) must refuse to drop a non-mock (live) database.

Regression guard for the 2026-07-09 incident: a bare `python -c` outside the
pytest/conftest isolation imported the app in live config and called
init_db(reset=True), which DROP-ALL'd the live paper_trader.db. A destructive
reset is only ever legitimate in mock mode (the sim clock restarts each run);
in any other provider it must fail closed, not wipe real trade history + ledger.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import session as sess_mod
from app.db.models import CapitalState


@pytest.fixture(autouse=True)
def own_database(tmp_path):
    """This file gets its own database, and it is not optional.

    These tests call `init_db(reset=True)`, which DROPs every table. Against the
    suite's shared per-run database that is two problems at once:

    * **it flaked.** `DROP TABLE` needs an exclusive lock, and in WAL mode a
      single session left open anywhere in a 2,500-test run holds a read
      transaction that blocks it past the 10s `busy_timeout` → "database is
      locked". It failed in roughly two runs in five, always here, and always
      taking `test_health_endpoint.py` down with it — those were ERRORs at
      fixture setup against a database this file had half-dropped, not defects
      of their own.
    * **it was a side effect.** A test that wipes the schema out from under
      every other test is relying on collection order to stay benign.

    An intermittent failure is worse than a red one here: this repository's
    working rule is that every claim about test results comes with the command
    and its output, and a suite that fails two runs in five makes every such
    claim negotiable.

    The redirection uses its **own** `MonkeyPatch`, not the tests' fixture. One
    of these tests calls `monkeypatch.undo()` mid-body to stop pretending it is
    live, and the fixture-injected instance is shared — so an `undo()` meant for
    one patch silently handed the database back too, and the test then read a
    database nobody had created.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'guard.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sess_mod, "engine", engine)
        mp.setattr(sess_mod, "SessionLocal",
                   sessionmaker(bind=engine, future=True, expire_on_commit=False))
        try:
            yield
        finally:
            engine.dispose()


def test_init_db_reset_refused_and_preserves_data_when_not_mock(monkeypatch):
    # arrange: clean mock DB with a sentinel cash value
    sess_mod.init_db(reset=True)  # mock mode — allowed
    with sess_mod.SessionLocal() as s:
        s.get(CapitalState, 1).cash = 12345.67
        s.commit()

    # act: pretend we're live and attempt a destructive reset
    class _Live:
        provider = "kite"

    monkeypatch.setattr(sess_mod, "get_settings", lambda: _Live())
    with pytest.raises(RuntimeError, match="mock"):
        sess_mod.init_db(reset=True)

    # assert: nothing was dropped — the sentinel row survived
    monkeypatch.undo()
    with sess_mod.SessionLocal() as s:
        assert s.get(CapitalState, 1).cash == 12345.67


def test_init_db_reset_allowed_in_mock():
    # the legitimate path: mock mode resets cleanly and reseeds, no raise
    sess_mod.init_db(reset=True)
    with sess_mod.SessionLocal() as s:
        assert s.get(CapitalState, 1) is not None


def test_init_db_no_reset_never_guarded(monkeypatch):
    # reset=False must work regardless of provider (this is the live startup path)
    class _Live:
        provider = "kite"
        initial_capital = 50000

    monkeypatch.setattr(sess_mod, "get_settings", lambda: _Live())
    sess_mod.init_db(reset=False)  # must not raise
