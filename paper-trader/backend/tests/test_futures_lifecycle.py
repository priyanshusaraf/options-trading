"""E2 step 12: the whole segment, flag ON, ledger paisa-exact throughout.

Every other futures test exercises one seam. This one runs the lifecycle the way
production would — enable, signal, size, open, mark, exit — and asserts the hard
invariant `cash == initial + realized − Σ(open entry_cost)` at every stage.

It is the test that would catch a defect none of the unit tests can: a segment
where each part is individually correct and the parts together lose a rupee.
The dryrun already proves this for options and equity; futures now has the same
proof, and it runs with the flag flipped on so the "it's disabled" answer cannot
hide anything.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.models import Trade
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.core import paper_authority
from app.db.models import LEGACY_DEPLOYMENT_ID
from tests.admitted_entry import persist_admitted_entry

NOW = dt.datetime(2026, 8, 3, 11, 0)


@pytest.fixture
def runner(monkeypatch, give_futures_price_feed):
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.armed = True
    cap = r.broker.capital()
    cap.initial_capital = 1_000_000.0
    cap.cash = 1_000_000.0
    r.broker.s.commit()
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as s:
        row = paper_authority.stage(s, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY", interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id); s.commit()
    with r._session() as s:
        from unittest.mock import patch
        d={"project_id":"test.admission.4c1029697ee358715d3a14a2","graph_identifier":"test.strategy.expanding_z_impulse","graph_version":1,"content_address":admission["graph_address"],"admission_address":admission["admission_address"],"decision":"approved"}
        with patch.object(paper_authority, "verified_decision", return_value=d):
            paper_authority.activate(s, row.id, revision=row.revision, owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        s.commit()
    r.refresh_paper_authority()
    r.params = {**r.params, "index_futures_enabled": True,
                "index_futures_max_positions": 1,
                "index_futures_max_margin": 250_000.0,
                "index_futures_min_margin": 50_000.0,
                # Lockstep OFF for the lifecycle test. Futures reuse
                # `_apply_lockstep` (spec: "direction-aware SL/TP + lockstep
                # reuse"), which RATCHETS both stop and target on every mark — so
                # a target captured before marking is stale by the time the exit
                # is evaluated. That behaviour has its own tests; here the subject
                # is the ledger across a plain open -> mark -> SL/TP -> close.
                "intraday_lockstep_enabled": False}
    r.publish_signal(
        "NIFTY", r._binding_for("NIFTY"), {"long_entry": True, "short_entry": False, "close": 24_000.0})
    give_futures_price_feed(r.provider,
                           lambda inst, expiry: 24_000.0)
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


def _drift(r) -> float:
    cap = r.broker.capital()
    open_cost = sum(p.entry_cost for p in r.broker.open_positions())
    return cap.cash - (cap.initial_capital + cap.realized_pnl - open_cost)


def _futs(r):
    return [p for p in r.broker.open_positions() if p.segment == "index_futures"]


def test_the_full_lifecycle_keeps_the_ledger_exact(runner, monkeypatch, give_futures_price_feed):
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6)

    runner._process_futures_entries(NOW)
    assert len(_futs(runner)) == 1
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6), "entry broke the invariant"

    pos = _futs(runner)[0]
    assert pos.entry_intent_id is not None
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: 24_120.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6), "marking moved cash"

    # Drive it to the target so the exit is the strategy's, not a force-flat.
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: pos.target_price + 1.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert _futs(runner) == [], "the target did not close the position"
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6), "exit broke the invariant"

    tr = runner.broker.s.query(Trade).all()[-1]
    assert tr.segment == "index_futures"
    assert tr.net_pnl > 0
    assert tr.charges_total > 0, "a round trip with no charges is not a real trade"


def test_a_losing_round_trip_also_reconciles(runner, monkeypatch, give_futures_price_feed):
    """Profit paths are the ones people test. The loss path moves cash the other
    way and is exactly as able to break the invariant."""
    runner._process_futures_entries(NOW)
    pos = _futs(runner)[0]
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: pos.stop_price - 1.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert _futs(runner) == []
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6)
    assert runner.broker.s.query(Trade).all()[-1].net_pnl < 0


def test_a_short_round_trip_reconciles(runner, monkeypatch, give_futures_price_feed):
    runner.publish_signal(
        "NIFTY", runner._binding_for("NIFTY"), {"long_entry": False, "short_entry": True, "close": 24_000.0})
    runner._process_futures_entries(NOW)
    pos = _futs(runner)[0]
    assert pos.direction == "SHORT"
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: pos.target_price - 1.0)
    runner._mark_exit_futures(pos, "NIFTY", NOW, {}, {"NIFTY": pos})
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6)
    assert runner.broker.s.query(Trade).all()[-1].net_pnl > 0


def test_a_force_flat_round_trip_reconciles(runner, monkeypatch):
    """The exit path that fires on every ordinary day."""
    from app.core import market_hours
    runner._process_futures_entries(NOW)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 5)
    runner.square_off_intraday(NOW)
    assert _futs(runner) == []
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6)


def test_turning_the_flag_back_off_leaves_no_residue(runner):
    """Enable, trade, disable: the segment must go quiet without stranding an
    open position or a half-booked ledger."""
    runner._process_futures_entries(NOW)
    open_before = len(_futs(runner))
    runner.params = {**runner.params, "index_futures_enabled": False}
    runner._process_futures_entries(NOW)
    assert len(_futs(runner)) == open_before, "opened while disabled"
    assert _drift(runner) == pytest.approx(0.0, abs=1e-6)
