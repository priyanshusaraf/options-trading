"""E1 — daily profit-lock (give-back guard): the symmetric twin of the daily-loss
halt, but on the upside. Once the day's realized+unrealized P&L clears a fraction
of the day's deployed capital, arm a give-back floor; if the day retraces to the
floor -> square off ALL open positions and halt new entries for the rest of the
session. Exits always run; the guard is OFF by default (lock_pct <= 0)."""
from __future__ import annotations

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.risk_controls import daily_profit_lock
from app.engine.runner import EngineRunner
from tests.admitted_entry import persist_admitted_entry


# ── pure function ──────────────────────────────────────────────────────────

def test_off_when_lock_pct_zero_or_negative():
    assert daily_profit_lock(10_000, 10_000, 100_000, 0.0, 0.5) == (False, None)
    assert daily_profit_lock(10_000, 10_000, 100_000, -0.1, 0.5) == (False, None)


def test_off_when_deployed_capital_non_positive():
    assert daily_profit_lock(10_000, 10_000, 0.0, 0.02, 0.5) == (False, None)
    assert daily_profit_lock(10_000, 10_000, -500.0, 0.02, 0.5) == (False, None)


def test_off_when_high_water_non_positive():
    assert daily_profit_lock(-10, 0.0, 100_000, 0.02, 0.5) == (False, None)
    assert daily_profit_lock(-10, -50, 100_000, 0.02, 0.5) == (False, None)


def test_not_armed_below_threshold():
    # deployed 100,000; lock_pct 2% -> arm threshold 2,000. high_water 1,999 -> not armed.
    assert daily_profit_lock(1_999, 1_999, 100_000, 0.02, 0.5) == (False, None)


def test_armed_but_not_breached():
    # armed at high_water=2,000 (== threshold); floor = 0.5 * 2000 = 1000. day_pnl 1500 > floor.
    breached, floor = daily_profit_lock(1_500, 2_000, 100_000, 0.02, 0.5)
    assert breached is False
    assert floor == 1_000.0


def test_armed_and_breached_exact_floor_value():
    # armed at high_water=4,000; floor = 0.5*4000 = 2000. day_pnl retraces to exactly 2000 -> breach.
    breached, floor = daily_profit_lock(2_000, 4_000, 100_000, 0.02, 0.5)
    assert breached is True
    assert floor == 2_000.0


def test_high_water_trailing_up_raises_the_floor():
    # same giveback_frac, higher high_water -> a higher floor.
    _, floor_a = daily_profit_lock(3_000, 3_000, 100_000, 0.02, 0.5)
    _, floor_b = daily_profit_lock(3_000, 6_000, 100_000, 0.02, 0.5)
    assert floor_b > floor_a
    assert floor_a == 1_500.0
    assert floor_b == 3_000.0


def test_giveback_frac_scales_floor():
    breached, floor = daily_profit_lock(3_000, 10_000, 100_000, 0.02, 0.3)
    assert floor == 3_000.0
    assert breached is True  # day_pnl (3000) <= floor (3000)
    breached2, floor2 = daily_profit_lock(3_001, 10_000, 100_000, 0.02, 0.3)
    assert breached2 is False
    assert floor2 == 3_000.0


# ── runner integration ─────────────────────────────────────────────────────

def _runner(lock_pct: float = 0.02, giveback_frac: float = 0.5) -> EngineRunner:
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.params["entry_min_days_to_expiry"] = 0
    r.params["daily_profit_lock_pct"] = lock_pct
    r.params["daily_profit_giveback_frac"] = giveback_frac
    return r


def _open_nifty(r: EngineRunner):
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    admission = persist_admitted_entry(r.broker.s)
    return r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot,
                                   r.params, **admission)


def test_climb_then_giveback_flattens_all_and_blocks_entries():
    r = _runner(lock_pct=0.02, giveback_frac=0.5)
    pos = _open_nifty(r)
    deployed = pos.entry_cost
    assert deployed > 0
    now = r.provider.now()

    # tick 1: day P&L climbs to +2% of deployed capital (arms the floor)
    peak_pnl = 0.02 * deployed + 5.0
    r._today_net_realized = lambda today: 0.0
    r._open_unrealized = lambda: peak_pnl
    r._maybe_profit_lock(now)
    assert r._pl_high_water == peak_pnl
    assert r._pl_halted_date is None   # armed, not yet breached

    # tick 2: retraces past the give-back floor (< 50% of peak)
    retraced_pnl = peak_pnl * 0.4
    r._open_unrealized = lambda: retraced_pnl
    r._maybe_profit_lock(now)

    assert r._pl_halted_date == now.date()
    assert len(r.broker.open_positions()) == 0     # flattened
    assert r.broker.position_for("NIFTY") is None

    # a subsequent entries-halted check blocks new entries the rest of the session
    assert r._entries_halted(now) is True
    status = r.halt_status(now)
    assert status["halted"] is True
    assert status["profit_lock_halted"] is True


def test_guard_off_by_default_does_not_flatten_on_same_giveback():
    r = _runner(lock_pct=0.0, giveback_frac=0.5)   # OFF
    pos = _open_nifty(r)
    deployed = pos.entry_cost
    now = r.provider.now()

    peak_pnl = 0.02 * deployed + 5.0
    r._today_net_realized = lambda today: 0.0
    r._open_unrealized = lambda: peak_pnl
    r._maybe_profit_lock(now)

    retraced_pnl = peak_pnl * 0.4
    r._open_unrealized = lambda: retraced_pnl
    r._maybe_profit_lock(now)

    assert r._pl_halted_date is None
    assert len(r.broker.open_positions()) == 1     # NOT flattened — guard is off
    assert r._entries_halted(now) is False


def test_high_water_trails_up_across_ticks_never_loosens():
    r = _runner(lock_pct=0.02, giveback_frac=0.5)
    pos = _open_nifty(r)
    deployed = pos.entry_cost
    now = r.provider.now()

    r._today_net_realized = lambda today: 0.0
    r._open_unrealized = lambda: 0.02 * deployed + 5.0
    r._maybe_profit_lock(now)
    hw1 = r._pl_high_water
    assert r._pl_halted_date is None

    # climbs further
    r._open_unrealized = lambda: 0.03 * deployed + 5.0
    r._maybe_profit_lock(now)
    hw2 = r._pl_high_water
    assert hw2 > hw1

    # dips a bit but stays above the give-back floor (0.5 * hw2) -> high water must
    # NOT drop back to the lower value.
    dip = hw2 * 0.6
    r._open_unrealized = lambda: dip
    r._maybe_profit_lock(now)
    assert r._pl_high_water == hw2       # never loosens
    assert r._pl_halted_date is None     # dip stayed above the floor


def test_kill_still_squares_off_everything_after_refactor():
    r = _runner()
    r.arm(True)
    _open_nifty(r)
    assert len(r.broker.open_positions()) == 1
    closed = r.kill()
    assert r.armed is False
    assert "NIFTY" in closed
    assert len(r.broker.open_positions()) == 0


@pytest.mark.parametrize("direction,sign,exit_side", [("LONG", 1, "SELL"), ("SHORT", -1, "BUY")])
def test_giveback_settles_futures_with_signed_pnl_and_margin_release(direction, sign, exit_side):
    import datetime as dt
    from sqlalchemy import select
    from app.db.models import Trade
    from tests.test_futures_broker import _open, _reconciles
    from unittest.mock import Mock
    runner = _runner()
    runner.notifier._send = lambda text: False
    broker = runner.broker
    try:
        initial_cash = broker.capital().cash
        broker._test_admission = persist_admitted_entry(broker.s)
        position = _open(broker, direction=direction)
        now = dt.datetime(2026, 8, 3, 12)
        exit_charge = Mock(wraps=broker._exit_charge_answer)
        broker._exit_charge_answer = exit_charge
        broker.mark(position, 24000 + sign * 500, 24000 + sign * 500, now)
        broker.commit()
        runner._maybe_profit_lock(now)
        assert runner._pl_halted_date is None
        broker.mark(position, 24000 + sign * 100, 24000 + sign * 100, now)
        broker.commit()
        runner._maybe_profit_lock(now)
        trade = broker.s.scalar(select(Trade).where(Trade.exit_reason == "PROFIT_LOCK"))
        assert trade.segment == "index_futures"
        assert trade.gross_pnl == 5000
        assert trade.net_pnl == pytest.approx(5000 - trade.charges_total)
        assert broker.capital().cash == pytest.approx(initial_cash + trade.net_pnl)
        assert _reconciles(broker) == pytest.approx(0, abs=1e-6)
        assert exit_charge.call_count == 1
        assert exit_charge.call_args.args[1] == exit_side
        assert broker.open_positions() == []
        assert runner._pl_halted_date == now.date()
    finally:
        broker.close()


def test_squareoff_keeps_failed_positions_and_routes_equity_and_options():
    import datetime as dt
    from types import SimpleNamespace
    from unittest.mock import Mock
    base = dict(entry_premium=10, last_premium=12, last_spot=100, tradingsymbol="test")
    failed = SimpleNamespace(**base, instrument_key="failed", segment="options")
    equity = SimpleNamespace(**base, instrument_key="equity", segment="equity_intraday")
    option = SimpleNamespace(**base, instrument_key="option", segment="options")
    runner = EngineRunner.__new__(EngineRunner)
    runner.broker = SimpleNamespace(open_positions=lambda: [failed, equity, option],
        close_position=Mock(side_effect=[None, object()]), close_equity_position=Mock(return_value=object()))
    runner.notifier = SimpleNamespace(clear=Mock())
    runner.state = {"failed": {"position": failed}, "equity": {"position": equity}}
    now = dt.datetime(2026, 9, 5, 12)
    assert runner._square_off_all("PROFIT_LOCK", now) == ["equity", "option"]
    runner.broker.close_equity_position.assert_called_once_with(equity, 12, "PROFIT_LOCK", now)
    assert runner.broker.close_position.call_count == 2
    assert runner.state["failed"]["position"] is failed
    assert runner.state["equity"]["position"] is None
    assert [call.args[0] for call in runner.notifier.clear.call_args_list] == ["equity", "option"]
