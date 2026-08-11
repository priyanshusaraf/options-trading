"""E0.3: peak-excursion telemetry (MFE/MAE per trade).

MFE = best unrealized P&L reached while open; MAE = worst. Both are computed from
Position.unrealized_pnl(), which is already segment/direction-aware (an equity SHORT
profits as price falls), so mark() is the single chokepoint that updates them for
both segments. This is pure telemetry — it must never perturb cash/realized_pnl/
entry_cost or any P&L figure the ledger invariant depends on.
"""
import datetime as dt
import os
import subprocess
import sys

import numpy as np
import pytest

from app.core.instruments import get_instrument
from app.engine.broker import PaperBroker
from app.db.session import init_db
from app.providers.mock import MockProvider

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOW = dt.datetime(2024, 1, 2, 10, 0)
PARAMS = {"intraday_leverage": 5.0, "intraday_stop_loss_pct": 0.5,
          "intraday_target_pct": 0.5}


def _broker() -> PaperBroker:
    init_db(reset=True)
    return PaperBroker(MockProvider(), broker_account_id="account.default")


def test_options_long_mfe_mae_exact():
    b = _broker()
    pos = b.open_position(get_instrument("NIFTY"), "LONG",
                          _quote(get_instrument("NIFTY"), 100.0), "t", NOW, spot=20000.0)
    qty = pos.qty
    assert pos.mfe == 0.0 and pos.mae == 0.0   # seeded at entry

    b.mark(pos, 160.0, 20100.0, NOW + dt.timedelta(minutes=1))   # peak favorable
    b.mark(pos, 80.0, 19900.0, NOW + dt.timedelta(minutes=2))    # peak adverse
    tr = b.close_position(pos, 90.0, "STRATEGY_EXIT", NOW + dt.timedelta(minutes=3), 19950.0)

    assert tr.mfe == pytest.approx((160.0 - 100.0) * qty)
    assert tr.mae == pytest.approx((80.0 - 100.0) * qty)
    assert tr.mae < 0 < tr.mfe


def test_equity_long_mfe_mae_match_spot_excursion():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "LONG", price=100.0, qty=200,
                                 charge_segment="NSE_INTRADAY", reason="t", now=NOW,
                                 params=PARAMS)
    assert pos.mfe == 0.0 and pos.mae == 0.0

    b.mark(pos, 110.0, 110.0, NOW + dt.timedelta(minutes=1))  # up (favorable for LONG)
    b.mark(pos, 95.0, 95.0, NOW + dt.timedelta(minutes=2))    # down (adverse for LONG)
    tr = b.close_equity_position(pos, 105.0, "TARGET", NOW + dt.timedelta(minutes=3))

    assert tr.mfe == pytest.approx((110.0 - 100.0) * 200)
    assert tr.mae == pytest.approx((95.0 - 100.0) * 200)


def test_equity_short_mfe_mae_are_direction_aware():
    b = _broker()
    pos = b.open_equity_position(get_instrument("NIFTY"), "SHORT", price=100.0, qty=200,
                                 charge_segment="NSE_INTRADAY", reason="t", now=NOW,
                                 params=PARAMS)
    assert pos.mfe == 0.0 and pos.mae == 0.0

    # favorable for a SHORT = price falls; adverse = price rises
    b.mark(pos, 90.0, 90.0, NOW + dt.timedelta(minutes=1))    # fall -> favorable
    b.mark(pos, 108.0, 108.0, NOW + dt.timedelta(minutes=2))  # rise -> adverse
    tr = b.close_equity_position(pos, 100.0, "STRATEGY_EXIT", NOW + dt.timedelta(minutes=3))

    assert tr.mfe == pytest.approx((100.0 - 90.0) * 200)     # positive: the fall
    assert tr.mae == pytest.approx((100.0 - 108.0) * 200)    # negative: the rise
    assert tr.mfe > 0 > tr.mae


def test_trade_that_only_moved_against_you_has_zero_mfe():
    b = _broker()
    pos = b.open_position(get_instrument("NIFTY"), "LONG",
                          _quote(get_instrument("NIFTY"), 100.0), "t", NOW, spot=20000.0)
    b.mark(pos, 90.0, 19900.0, NOW + dt.timedelta(minutes=1))
    b.mark(pos, 70.0, 19800.0, NOW + dt.timedelta(minutes=2))
    tr = b.close_position(pos, 70.0, "STOP_LOSS", NOW + dt.timedelta(minutes=3), 19800.0)

    assert tr.mfe == 0.0          # never traded above entry
    assert tr.mae < 0.0


def test_excursion_telemetry_does_not_perturb_ledger():
    """Same close as a plain round trip must reconcile identically whether or not
    MFE/MAE moved — telemetry must never touch cash/realized_pnl/entry_cost."""
    b = _broker()
    pos = b.open_position(get_instrument("NIFTY"), "LONG",
                          _quote(get_instrument("NIFTY"), 100.0), "t", NOW, spot=20000.0)
    b.mark(pos, 160.0, 20100.0, NOW + dt.timedelta(minutes=1))
    b.mark(pos, 80.0, 19900.0, NOW + dt.timedelta(minutes=2))
    tr = b.close_position(pos, 90.0, "STRATEGY_EXIT", NOW + dt.timedelta(minutes=3), 19950.0)

    assert tr.net_pnl == pytest.approx(tr.gross_pnl - tr.charges_total)
    assert b.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)


def test_partial_close_carries_excursion_so_far():
    b = _broker()
    pos = b.open_position(get_instrument("NIFTY"), "LONG",
                          _quote(get_instrument("NIFTY"), 100.0), "t", NOW, spot=20000.0)
    qty = pos.qty
    b.mark(pos, 150.0, 20050.0, NOW + dt.timedelta(minutes=1))
    b.mark(pos, 85.0, 19950.0, NOW + dt.timedelta(minutes=2))
    half = qty // 2 or 1
    tr = b.book_partial_close(pos, half, 120.0, "PARTIAL", NOW + dt.timedelta(minutes=3), 20000.0)

    assert tr.mfe == pytest.approx((150.0 - 100.0) * qty)
    assert tr.mae == pytest.approx((85.0 - 100.0) * qty)
    # the remaining open position keeps its excursion-so-far, unreset
    assert pos.mfe == pytest.approx((150.0 - 100.0) * qty)
    assert pos.mae == pytest.approx((85.0 - 100.0) * qty)


def test_mark_stores_python_float_not_numpy():
    """Regression: mock provider feeds numpy.float64 premiums/spots, so
    pos.unrealized_pnl() returns numpy.float64. Writing that straight into
    pos.mfe/pos.mae (ORM-mapped Float columns) corrupts SQLAlchemy's
    unit-of-work change bookkeeping and intermittently surfaces as a
    StaleDataError on the next commit in mark_and_exit_positions. mark() must
    cast to a plain Python float before assigning.
    """
    b = _broker()
    pos = b.open_position(get_instrument("NIFTY"), "LONG",
                          _quote(get_instrument("NIFTY"), 100.0), "t", NOW, spot=20000.0)

    b.mark(pos, np.float64(160.0), np.float64(20100.0), NOW + dt.timedelta(minutes=1))
    assert type(pos.mfe) is float
    assert type(pos.mae) is float

    # drive mae negative with another numpy value and re-assert the type
    b.mark(pos, np.float64(80.0), np.float64(19900.0), NOW + dt.timedelta(minutes=2))
    assert pos.mae < 0
    assert type(pos.mfe) is float
    assert type(pos.mae) is float


def test_dryrun_seed6_ledger_exact_under_excursion():
    """Integration guard for the same bug: PYTHONHASHSEED=6 drives the mock
    provider's price path to deterministically hit the numpy-write bug within
    700 ticks (it was intermittent under other seeds because the mock's path
    depends on hash()). Baseline/pre-E0.3 passes this seed; the numpy-write
    version of mark() fails it with a StaleDataError during
    mark_and_exit_positions.
    """
    env = {**os.environ, "PYTHONHASHSEED": "6"}
    out = subprocess.run(
        [sys.executable, "scripts/dryrun.py", "700"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert "LEDGER OK" in out.stdout, out.stdout[-2000:] + out.stderr[-2000:]
    assert out.returncode == 0


def _quote(inst, ltp: float):
    """Build a minimal OptionQuote for open_position, matching the real dataclass shape."""
    from app.providers.base import OptionQuote
    return OptionQuote(
        instrument_key=inst.key, tradingsymbol=f"{inst.key}24JAN20000CE",
        exchange=inst.segment, strike=20000.0, expiry=dt.date(2024, 1, 25),
        option_type="CE", lot_size=50, ltp=ltp, bid=ltp - 0.5, ask=ltp + 0.5,
        volume=1000, oi=10000,
    )
