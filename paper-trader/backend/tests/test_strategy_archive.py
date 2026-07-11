"""Strategy archive/lifecycle: every strategy the platform has ever considered, with
its current state — candidate → running → probation → on_hold → retired — and the
transitions that are allowed between them. Retired strategies are REVIVABLE (a shelved
idea can be brought back and re-tested), which is the whole point of keeping the archive.
"""
import pytest

from app.core import strategy_archive as arch
from app.db.models import StrategyLifecycle
from app.db.session import SessionLocal, init_db


def _fresh():
    init_db(reset=True)


def test_record_defaults_to_candidate_and_is_idempotent():
    _fresh()
    with SessionLocal() as s:
        r1 = arch.record_strategy(s, "trend_impulse_v3")
        s.commit()
        assert r1.status == "candidate"
        r2 = arch.record_strategy(s, "trend_impulse_v3")
        s.commit()
        assert r2.id == r1.id
        assert s.query(StrategyLifecycle).count() == 1


def test_valid_transition_updates_status():
    _fresh()
    with SessionLocal() as s:
        arch.record_strategy(s, "x")
        s.commit()
        arch.set_status(s, "x", "running", note="deployed to Bullion")
        s.commit()
        got = arch.get(s, "x")
        assert got.status == "running" and got.note == "deployed to Bullion"


def test_invalid_transition_is_rejected():
    _fresh()
    with SessionLocal() as s:
        arch.record_strategy(s, "x")            # candidate
        s.commit()
        with pytest.raises(ValueError):
            arch.set_status(s, "x", "probation")  # candidate -> probation is not allowed


def test_retired_strategy_can_be_revived():
    _fresh()
    with SessionLocal() as s:
        arch.record_strategy(s, "x")
        s.commit()
        arch.set_status(s, "x", "running")
        arch.set_status(s, "x", "retired")
        s.commit()
        arch.set_status(s, "x", "candidate")     # revival
        s.commit()
        assert arch.get(s, "x").status == "candidate"


def test_by_status_and_list_archive():
    _fresh()
    with SessionLocal() as s:
        arch.record_strategy(s, "a")
        arch.record_strategy(s, "b")
        s.commit()
        arch.set_status(s, "a", "running")
        s.commit()
        assert [r.strategy_key for r in arch.by_status(s, "running")] == ["a"]
        assert {d["strategy_key"] for d in arch.list_archive(s)} == {"a", "b"}
