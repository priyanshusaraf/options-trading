"""DB session hygiene on the watchlist-mutation path.

`_upsert_state` used to hand an OPEN session back to its callers, each of which
ended with `s.commit(); s.close()`. Any exception in between — a failed commit, a
validation raise, a bug in the lines that follow — skipped the close, leaking the
session and its pooled connection. SQLAlchemy eventually reclaims those on GC, so
it never shows up as a clean failure; it shows up the way 2026-07-23 did, as pool
pressure under load with `/api/health` still answering 200.

These tests pin the connection accounting directly, because "the code reads
better now" is not evidence that a leak is fixed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.models import InstrumentState
from app.db.session import SessionLocal, engine, init_db
from app.engine.runner import EngineRunner


@pytest.fixture
def runner():
    init_db(reset=True)
    return EngineRunner(owner_id="owner", broker_account_id="account.default")


def _checked_out() -> int:
    """Connections currently held out of the pool."""
    return engine.pool.checkedout()


# ── the leak ────────────────────────────────────────────────────────────────

def test_a_failed_write_does_not_leak_a_connection(runner, monkeypatch):
    """The regression this exists for: raise where the old code would have
    skipped its `s.close()`, and prove the pool is whole afterwards."""
    before = _checked_out()

    class _Boom(Exception):
        pass

    def _explode(self, *a, **kw):
        raise _Boom("commit failed")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", _explode)
    with pytest.raises(_Boom):
        runner.set_priority_flag("NIFTY", True)

    assert _checked_out() == before, \
        "a failed watchlist write leaked its connection back into the pool count"


def test_a_successful_write_does_not_leak_a_connection(runner):
    before = _checked_out()
    runner.set_priority_flag("NIFTY", True)
    assert _checked_out() == before


def test_repeated_writes_do_not_accumulate_connections(runner):
    """One leak is a bug; a leak on a route the UI can call in a loop is an outage."""
    runner.set_priority_flag("NIFTY", True)      # warm the pool first
    before = _checked_out()
    for i in range(25):
        runner.set_priority_flag("NIFTY", bool(i % 2))
    assert _checked_out() == before


# ── it still has to do the job ──────────────────────────────────────────────

def test_the_flag_is_actually_persisted(runner):
    runner.set_priority_flag("NIFTY", True)
    with SessionLocal() as s:
        assert s.get(InstrumentState, "NIFTY").priority_flag is True
    runner.set_priority_flag("NIFTY", False)
    with SessionLocal() as s:
        assert s.get(InstrumentState, "NIFTY").priority_flag is False


def test_a_row_is_created_for_an_instrument_that_has_none(runner):
    """The whole point of an UPSERT: a freshly added instrument has no row yet."""
    key = "NEWLY_ADDED_KEY"
    with SessionLocal() as s:
        assert s.get(InstrumentState, key) is None
    runner.set_priority_flag(key, True)
    with SessionLocal() as s:
        assert s.get(InstrumentState, key).priority_flag is True


def test_a_failed_write_leaves_no_half_applied_row(runner, monkeypatch):
    """Rollback, not just close. A partially-applied watchlist row is the kind of
    state bug that reappears three restarts later as an unexplained setting."""
    key = "ROLLBACK_KEY"

    real_commit = __import__("sqlalchemy").orm.Session.commit

    def _explode(self, *a, **kw):
        raise RuntimeError("commit failed")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", _explode)
    with pytest.raises(RuntimeError):
        runner.set_priority_flag(key, True)
    monkeypatch.setattr("sqlalchemy.orm.Session.commit", real_commit)

    with SessionLocal() as s:
        assert s.get(InstrumentState, key) is None, \
            "the uncommitted row survived the failed write"


def test_in_memory_state_does_not_advance_past_a_failed_write(runner, monkeypatch):
    """If the DB write fails, the engine's in-memory view must not claim success —
    otherwise the running engine and the persisted book disagree until restart."""
    runner.priority_flags.pop("NIFTY", None)

    def _explode(self, *a, **kw):
        raise RuntimeError("commit failed")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", _explode)
    with pytest.raises(RuntimeError):
        runner.set_priority_flag("NIFTY", True)

    assert "NIFTY" not in runner.priority_flags


# ── engine/pool configuration ───────────────────────────────────────────────

def test_pool_pre_ping_is_on():
    """A connection handed out after the DB file was replaced (deploy, VACUUM,
    restore) is dead on arrival; pre_ping turns that into a reconnect instead of
    an error surfacing in whatever request drew the bad connection."""
    assert engine.pool._pre_ping is True


def test_the_connection_still_works_end_to_end():
    """Guard the pool settings against a typo that configures an unusable engine."""
    with SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
