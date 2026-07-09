"""init_db(reset=True) must refuse to drop a non-mock (live) database.

Regression guard for the 2026-07-09 incident: a bare `python -c` outside the
pytest/conftest isolation imported the app in live config and called
init_db(reset=True), which DROP-ALL'd the live paper_trader.db. A destructive
reset is only ever legitimate in mock mode (the sim clock restarts each run);
in any other provider it must fail closed, not wipe real trade history + ledger.
"""
import pytest

from app.db import session as sess_mod
from app.db.models import CapitalState


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
