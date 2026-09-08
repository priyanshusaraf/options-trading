"""The kill switch must do as much as it can, even when parts of it fail.

It is the control you reach for when things are already going wrong — which is
precisely when a broker call is most likely to throw. A kill that aborts halfway
because one step raised leaves the operator believing they stopped the bot while
positions are still open and unmanaged.

So the contract is: ALWAYS disarm, then attempt every remaining step
independently, and report what actually happened. Best-effort, never all-or-
nothing.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from tests.admitted_entry import persist_admitted_entry


@pytest.fixture
def runner():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.armed = True
    cap = r.broker.capital()
    cap.initial_capital = 500_000.0
    cap.cash = 500_000.0
    r.broker.s.commit()
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


def _open_one(r):
    admission = persist_admitted_entry(r.broker.s)
    return r.broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", 50.0, 100, "NSE_INTRADAY", "TEST",
        dt.datetime(2026, 8, 3, 10, 0), r.params, margin=5_000.0, **admission)


def test_kill_disarms_and_flattens(runner):
    _open_one(runner)
    runner.kill(dt.datetime(2026, 8, 3, 12, 0))
    assert runner.armed is False
    assert runner.broker.open_positions() == []


def test_kill_still_flattens_when_cancelling_orders_fails(runner, monkeypatch):
    """The one that matters. A broker error while cancelling working entries must
    not prevent the square-off — the operator pressed KILL because they wanted
    the positions gone, and a half-completed kill is worse than an obvious
    failure because it looks like success."""
    _open_one(runner)
    monkeypatch.setattr(runner.broker, "cancel_working_entries",
                        lambda: (_ for _ in ()).throw(RuntimeError("broker down")))
    runner.kill(dt.datetime(2026, 8, 3, 12, 0))
    assert runner.armed is False, "kill must always disarm"
    assert runner.broker.open_positions() == [], \
        "a failed cancel prevented the square-off"


def test_kill_disarms_even_if_the_squareoff_fails(runner, monkeypatch):
    """Disarming is the one step that cannot be allowed to fail: it is what stops
    the engine opening MORE positions while the operator is trying to stop it."""
    _open_one(runner)
    monkeypatch.setattr(runner, "_square_off_all",
                        lambda reason, now: (_ for _ in ()).throw(RuntimeError("db down")))
    runner.kill(dt.datetime(2026, 8, 3, 12, 0))
    assert runner.armed is False


def test_kill_does_not_raise_at_the_caller(runner, monkeypatch):
    """It is wired to an API route and a UI button. An exception there shows the
    operator an error and tells them nothing about what was actually stopped."""
    _open_one(runner)
    monkeypatch.setattr(runner.broker, "cancel_working_entries",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(runner, "_square_off_all",
                        lambda reason, now: (_ for _ in ()).throw(RuntimeError("boom")))
    runner.kill(dt.datetime(2026, 8, 3, 12, 0))    # must not raise
    assert runner.armed is False


def test_kill_reports_what_it_actually_closed(runner):
    _open_one(runner)
    closed = runner.kill(dt.datetime(2026, 8, 3, 12, 0))
    assert len(closed) == 1


def test_kill_without_squareoff_still_disarms(runner):
    """square_off=False is the 'stop trading but leave my positions' variant."""
    _open_one(runner)
    runner.kill(dt.datetime(2026, 8, 3, 12, 0), square_off=False)
    assert runner.armed is False
    assert len(runner.broker.open_positions()) == 1
