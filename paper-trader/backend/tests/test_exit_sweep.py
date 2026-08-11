"""C-P2 — replay real closed trades under different exit parameters.

Production evidence (2026-08-01): across 72 real trades, `TARGET` has fired ZERO times.
Every exit the engine chose itself is net −₹2,927; every rupee of profit in the book came
from the owner closing manually. The exit parameters have been retuned by hand, blind,
because nothing could answer "what WOULD these settings have produced?".

MFE/MAE telemetry (landed 2026-07-24) makes that answerable — but only approximately, and
the approximation's limit is the whole point: MFE and MAE are two scalars, so when a trade
would have touched BOTH a candidate stop and a candidate target we cannot know which came
first. That ambiguity is reported as a band, never silently resolved. A sweep that hides it
would manufacture confidence and re-run exactly the mistake it exists to fix.
"""
import sqlite3

import pytest

from app.backtest.exit_sweep import ExitParams, ReplayTrade, replay, sweep
from scripts.exit_sweep import _rows_from_db


def test_db_sweep_requires_an_explicit_owner_and_broker_account_scope(tmp_path):
    db = tmp_path / "trades.db"
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE trades (exit_time TEXT)")
        con.commit()
    finally:
        con.close()
    with pytest.raises(ValueError, match="owner.*broker account"):
        _rows_from_db(str(db), None, None, owner_id=None, broker_account_id=None)


def _t(**over):
    """A LONG that peaked +₹800 and dipped −₹200, actually closed at +₹300."""
    kw = dict(tradingsymbol="X", direction="LONG", entry_price=100.0, qty=100,
              mfe=800.0, mae=-200.0, net_pnl=300.0, charges=40.0)
    kw.update(over)
    return ReplayTrade(**kw)


# ── the mechanics ────────────────────────────────────────────────────────────

def test_target_is_taken_when_the_peak_reached_it():
    """Notional 100×100 = ₹10,000; a 5% target is ₹500 and the trade peaked at ₹800."""
    r = replay(_t(), ExitParams(stop_pct=0.05, target_pct=0.05))
    assert r.reason == "TARGET"
    assert r.pnl == 500.0 - 40.0


def test_stop_is_taken_when_the_dip_reached_it():
    r = replay(_t(mfe=100.0), ExitParams(stop_pct=0.01, target_pct=0.10))
    assert r.reason == "STOP_LOSS"
    assert r.pnl == -100.0 - 40.0


def test_untouched_parameters_leave_the_real_outcome_alone():
    """Neither level reached → the trade ended however it really ended. Substituting a
    guess here would let the sweep 'improve' trades it never touched."""
    r = replay(_t(), ExitParams(stop_pct=0.50, target_pct=0.50))
    assert r.reason == "ACTUAL"
    assert r.pnl == 300.0


def test_both_levels_touched_is_reported_as_ambiguous_not_guessed():
    """MFE ₹800 clears a ₹300 target AND MAE −₹200 clears a ₹100 stop. Which came first
    is unknowable from two scalars, so the outcome is a band, not a number."""
    r = replay(_t(), ExitParams(stop_pct=0.01, target_pct=0.03))
    assert r.ambiguous is True
    assert r.pnl_pessimistic == -100.0 - 40.0
    assert r.pnl_optimistic == 300.0 - 40.0
    assert r.pnl == r.pnl_pessimistic          # the headline number is the safe one


def test_unambiguous_outcomes_have_a_zero_width_band():
    r = replay(_t(), ExitParams(stop_pct=0.05, target_pct=0.05))
    assert r.ambiguous is False
    assert r.pnl_pessimistic == r.pnl_optimistic == r.pnl


# ── profit lock ──────────────────────────────────────────────────────────────

def test_profit_lock_catches_a_winner_that_gave_it_all_back():
    """The production failure mode: peaked +₹800, actually closed +₹50. A lock armed at
    ₹450 keeping 30% of the peak would have booked ₹240."""
    r = replay(_t(net_pnl=50.0),
               ExitParams(stop_pct=0.50, target_pct=0.50,
                          lock_threshold=450.0, lock_frac=0.30))
    assert r.reason == "PROFIT_LOCK"
    assert r.pnl == 800.0 * 0.30 - 40.0


def test_profit_lock_never_makes_a_trade_worse_than_it_really_was():
    """If the real exit beat the lock floor, the lock would not have fired first."""
    r = replay(_t(net_pnl=700.0),
               ExitParams(stop_pct=0.50, target_pct=0.50,
                          lock_threshold=450.0, lock_frac=0.30))
    assert r.reason == "ACTUAL"
    assert r.pnl == 700.0


def test_profit_lock_does_not_arm_below_its_threshold():
    r = replay(_t(mfe=300.0, net_pnl=10.0),
               ExitParams(stop_pct=0.50, target_pct=0.50,
                          lock_threshold=450.0, lock_frac=0.30))
    assert r.reason == "ACTUAL"


def test_stop_beats_the_lock_when_both_would_fire():
    """Precedence must mirror the live engine: the protective stop is checked first."""
    r = replay(_t(mae=-900.0, net_pnl=-50.0),
               ExitParams(stop_pct=0.02, target_pct=0.50,
                          lock_threshold=450.0, lock_frac=0.30))
    assert r.reason in ("STOP_LOSS", "AMBIGUOUS_STOP_LOCK")
    assert r.pnl <= 0


# ── shorts ───────────────────────────────────────────────────────────────────

def test_short_side_uses_the_same_rupee_excursions():
    """MFE/MAE are already signed in rupees-in-your-favour terms, so direction only
    matters for reading the numbers, never for the arithmetic."""
    long_r = replay(_t(direction="LONG"), ExitParams(stop_pct=0.05, target_pct=0.05))
    short_r = replay(_t(direction="SHORT"), ExitParams(stop_pct=0.05, target_pct=0.05))
    assert long_r.pnl == short_r.pnl


# ── the sweep ────────────────────────────────────────────────────────────────

def test_sweep_ranks_parameter_sets_and_reports_the_ambiguity():
    trades = [_t(), _t(mfe=1200.0, mae=-90.0, net_pnl=100.0),
              _t(mfe=60.0, mae=-700.0, net_pnl=-650.0)]
    grid = [ExitParams(stop_pct=0.01, target_pct=0.03),
            ExitParams(stop_pct=0.05, target_pct=0.05),
            ExitParams(stop_pct=0.02, target_pct=0.02, lock_threshold=450, lock_frac=0.3)]
    out = sweep(trades, grid)

    assert len(out) == 3
    assert out == sorted(out, key=lambda r: -r.total_pnl)     # best first
    for row in out:
        assert row.trades == 3
        assert row.total_pnl_pessimistic <= row.total_pnl <= row.total_pnl_optimistic
        assert 0.0 <= row.win_rate <= 1.0
        assert sum(row.reasons.values()) == 3


def test_sweep_flags_a_result_that_rests_on_ambiguous_trades():
    """A parameter set whose edge comes entirely from coin-flips must not be presented as
    a winner — this is the guard against tuning on noise."""
    trades = [_t(), _t(), _t()]
    out = sweep(trades, [ExitParams(stop_pct=0.01, target_pct=0.03)])
    assert out[0].ambiguous_trades == 3
    assert out[0].trustworthy is False


def test_a_clean_result_is_marked_trustworthy():
    trades = [_t(mae=-10.0), _t(mae=-10.0), _t(mae=-10.0)]
    out = sweep(trades, [ExitParams(stop_pct=0.05, target_pct=0.05)])
    assert out[0].ambiguous_trades == 0
    assert out[0].trustworthy is True


def test_sweep_on_no_trades_is_empty_not_a_confident_zero():
    assert sweep([], [ExitParams(stop_pct=0.01, target_pct=0.01)]) == []


def test_trades_without_excursion_telemetry_are_excluded_and_counted():
    """Trades booked before MFE/MAE landed carry NULLs. Silently treating those as
    'never moved' would drag every result toward the actual outcome and look like
    the parameters barely matter."""
    trades = [_t(), ReplayTrade("OLD", "LONG", 100.0, 100, None, None, 20.0, 40.0)]
    out = sweep(trades, [ExitParams(stop_pct=0.05, target_pct=0.05)])
    assert out[0].trades == 1
    assert out[0].skipped_no_telemetry == 1


def test_pre_telemetry_zero_rows_are_excluded_not_read_as_flat_trades():
    """The real production trap: rows booked before 2026-07-24 carry 0.0/0.0 from the ORM
    default, not NULL. Treating them as trades that never moved would collapse every
    candidate policy onto the actual outcome and hide the parameters' effect entirely."""
    flat = ReplayTrade("PRE", "SHORT", 53.12, 940, 0.0, 0.0, -12.34, 52.92)
    assert flat.has_telemetry is False

    # ... while a genuine trade that never went green (MFE 0, MAE negative) is REAL data.
    never_green = ReplayTrade("INDIGO", "SHORT", 5234.0, 4, 0.0, -107.0, -129.1, 20.0)
    assert never_green.has_telemetry is True

    out = sweep([_t(), flat, never_green], [ExitParams(stop_pct=0.05, target_pct=0.05)])
    assert out[0].trades == 2
    assert out[0].skipped_no_telemetry == 1
