"""L1 Stage 1 — what a recorded disagreement must carry, and what it must never do.

A disagreement is only worth recording if it can be attributed afterwards to an exact
graph, an exact bar and an exact input frame. These tests pin every field the owner
required, plus the two properties that keep the record from becoming a liability: it is
written on its own database session (a shadow failure must not poison the engine's shared
session) and it can never take the signal lane down.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import IrShadowDivergence
from app.db.session import SessionLocal, init_db
from app.engine import ir_shadow
from app.engine import ir_shadow_store as store
from tests.legacy_money_scope import LegacyMoneyScope

store = LegacyMoneyScope(store, "record", "recent", "counts_by_reason", "prune")

from .test_ir_adapter import frame
from .test_ir_shadow import authoritative, series

NOW = dt.datetime(2026, 8, 4, 10, 30, 0)


def observation(**overrides) -> ir_shadow.ShadowObservation:
    df = frame(series())
    obs = ir_shadow.observe(
        instrument_key="SILVERM", authoritative_key="expanding_z_v4",
        authoritative_frame=authoritative(df), frame=df, now=NOW)
    values = {**obs.__dict__, **overrides}
    return ir_shadow.ShadowObservation(**values)


def diverged(**overrides) -> ir_shadow.ShadowObservation:
    flipped = {**observation().authoritative}
    flipped["longEntry"] = not flipped["longEntry"]
    return observation(reason=ir_shadow.FLAG_DIVERGENCE,
                       detail="longEntry: authoritative=True ir=False",
                       authoritative=flipped, **overrides)


def rows() -> list[IrShadowDivergence]:
    with SessionLocal() as session:
        return list(session.scalars(select(IrShadowDivergence)))


def setup_function() -> None:
    init_db(reset=True)


# ── what gets written ─────────────────────────────────────────────────────────────

def test_a_disagreement_is_persisted_with_everything_needed_to_attribute_it():
    obs = diverged()
    assert store.record(obs, market_open=True) is True

    (row,) = rows()
    assert row.observed_at == NOW
    assert row.instrument_key == "SILVERM"
    assert row.graph_address == obs.graph_address
    assert row.shadow_strategy_key == "ir.strategy.expanding_z_impulse"
    assert row.authoritative_strategy_key == "expanding_z_v4"
    assert row.authoritative_json and "longEntry" in row.authoritative_json
    assert row.ir_json and "longEntry" in row.ir_json
    assert row.warmup_state == "settled"
    assert row.declared_warmup == obs.declared_warmup
    assert row.frame_id == obs.frame_id
    assert row.frame_bars == obs.frame_bars
    assert row.frame_first_ts is not None and row.frame_last_ts is not None
    assert row.bar_time is not None
    assert row.reason == ir_shadow.FLAG_DIVERGENCE
    assert "longEntry" in row.detail
    assert row.eval_ms >= 0.0
    assert row.market_open is True


def test_an_agreement_is_counted_but_never_persisted():
    """The table is a disagreement record. Persisting every agreeing bar would put tens of
    thousands of rows a week on a 1 GB box for no information."""
    assert store.record(observation(), market_open=True) is False
    assert rows() == []


def test_a_refusal_records_the_absent_ir_verdict_as_absent_not_as_false():
    """`ir_json` must distinguish "the graph refused" from "the graph said all-False" —
    collapsing them is the exact silent-degradation shape Stage 0 existed to close."""
    obs = observation(reason=ir_shadow.INSUFFICIENT_HISTORY, ir=None,
                      warmup_state="insufficient", detail="134 bars, warmup 302")
    assert store.record(obs, market_open=True) is True
    (row,) = rows()
    assert row.ir_json is None
    assert row.warmup_state == "insufficient"


def test_the_same_bar_is_recorded_once_however_often_it_is_rescanned():
    """The signal lane re-scans the same completed bar every 2.5 s until the next one
    prints. One bar, one graph, one reason is one row."""
    obs = diverged()
    assert store.record(obs, market_open=True) is True
    assert store.record(obs, market_open=True) is False
    assert len(rows()) == 1


def test_a_different_bar_on_the_same_instrument_is_its_own_row():
    assert store.record(diverged(), market_open=True) is True
    later = diverged(bar_time=NOW + dt.timedelta(minutes=15))
    assert store.record(later, market_open=True) is True
    assert len(rows()) == 2


# ── the record can never hurt the engine ──────────────────────────────────────────

def test_a_store_failure_is_contained_and_reported_as_not_written():
    """Requirement 5. A broken shadow store returns False and logs; it never raises into
    the signal lane."""
    class Exploding:
        def __call__(self, *_a, **_k):
            raise RuntimeError("database is gone")

    original = store.SessionLocal
    store.SessionLocal = Exploding()
    try:
        assert store.record(diverged(), market_open=True) is False
    finally:
        store.SessionLocal = original


def test_the_store_uses_its_own_session_not_the_engine_shared_one():
    """`app/engine/runner.py` holds one shared session under a lock across both lanes; a
    failed write on that session poisons it for the authoritative path (H3). The shadow
    store therefore opens and closes its own."""
    import inspect
    source = inspect.getsource(store._module)
    assert "SessionLocal()" in source


# ── bounded growth on a 1 GB box ──────────────────────────────────────────────────

def test_old_divergences_are_prunable_and_recent_ones_are_kept():
    assert store.record(diverged(observed_at=NOW - dt.timedelta(days=90)),
                        market_open=True) is True
    assert store.record(diverged(observed_at=NOW,
                                 bar_time=NOW + dt.timedelta(minutes=15)),
                        market_open=True) is True

    assert store.prune(cutoff=NOW - dt.timedelta(days=30)) == 1
    assert [row.observed_at for row in rows()] == [NOW]


def test_pruning_with_no_cutoff_deletes_nothing():
    """Retention's standing rule here: 0 days means keep, never "delete everything"."""
    store.record(diverged(), market_open=True)
    assert store.prune(cutoff=None) == 0
    assert len(rows()) == 1
