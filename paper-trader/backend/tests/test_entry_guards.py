"""Pure entry-guard tests (added during the 2026-06-30 hardening pass)."""
import datetime as dt

from app.core.market_hours import IST
from app.engine.risk_controls import (
    expiry_too_close, intraday_blocked_for_expiry_day, outside_trading_session,
    round_trip_cap_reached, signal_already_evaluated)

TODAY = dt.date(2026, 6, 30)
TUE = dt.date(2026, 6, 30)   # a Tuesday (NIFTY-50 weekly expiry)
WED = dt.date(2026, 7, 1)    # a Wednesday


# ── #1 options DTE guard: block opening an option within N days of expiry ──
def test_expiry_blocks_zero_dte():
    assert expiry_too_close(dt.date(2026, 6, 30), TODAY, 3) is True   # 0 DTE


def test_expiry_blocks_one_and_two_dte():
    assert expiry_too_close(dt.date(2026, 7, 1), TODAY, 3) is True    # 1 DTE
    assert expiry_too_close(dt.date(2026, 7, 2), TODAY, 3) is True    # 2 DTE


def test_expiry_allows_three_dte():
    assert expiry_too_close(dt.date(2026, 7, 3), TODAY, 3) is False   # 3 DTE — allowed


def test_expiry_allows_far_expiry():
    assert expiry_too_close(dt.date(2026, 7, 30), TODAY, 3) is False


def test_expiry_guard_disabled_when_min_zero():
    assert expiry_too_close(dt.date(2026, 6, 30), TODAY, 0) is False


def test_expiry_none_never_blocks():
    assert expiry_too_close(None, TODAY, 3) is False


# ── #12 fresh-signal-only: a candle's signal is evaluated once, never re-queued ──
def test_fresh_signal_first_time_proceeds():
    assert signal_already_evaluated(1000, None) is False       # never evaluated → proceed


def test_fresh_signal_same_bar_skipped():
    assert signal_already_evaluated(1000, 1000) is True        # already evaluated this candle → skip


def test_fresh_signal_newer_bar_proceeds():
    assert signal_already_evaluated(2000, 1000) is False       # next candle → fresh → proceed


def test_fresh_signal_older_bar_skipped():
    assert signal_already_evaluated(500, 1000) is True         # stale / out-of-order → skip


def test_fresh_signal_missing_bar_never_blocks():
    assert signal_already_evaluated(None, 1000) is False


# ── #9 no-Tuesday-intraday (NIFTY expiry) unless opted in for that exact day ──
def test_tuesday_intraday_blocked():
    assert intraday_blocked_for_expiry_day(TUE, "", 1) is True


def test_non_tuesday_intraday_allowed():
    assert intraday_blocked_for_expiry_day(WED, "", 1) is False


def test_tuesday_override_for_today_allows():
    assert intraday_blocked_for_expiry_day(TUE, "2026-06-30", 1) is False


def test_tuesday_stale_override_still_blocks():
    assert intraday_blocked_for_expiry_day(TUE, "2026-06-23", 1) is True   # last Tue's opt-in doesn't carry


def test_tuesday_garbage_override_blocks():
    assert intraday_blocked_for_expiry_day(TUE, "not-a-date", 1) is True


def test_intraday_weekday_guard_disabled():
    assert intraday_blocked_for_expiry_day(TUE, "", -1) is False


# ── #16 continuous-session guard: never OPEN a new position outside continuous
# trading. A pre-open protected-limit rests until the 09:15 uncross and can miss it
# entirely — the LODHA 09:01:25 order that never filled (2026-07-03 live incident). ──
def test_entry_blocked_in_preopen():
    assert outside_trading_session("NSE", dt.datetime(2026, 7, 3, 9, 1, tzinfo=IST)) is True   # pre-open


def test_entry_allowed_in_continuous_session():
    assert outside_trading_session("NSE", dt.datetime(2026, 7, 3, 11, 0, tzinfo=IST)) is False


def test_entry_blocked_after_close():
    assert outside_trading_session("NSE", dt.datetime(2026, 7, 3, 15, 45, tzinfo=IST)) is True


def test_entry_blocked_on_weekend():
    assert outside_trading_session("NSE", dt.datetime(2026, 7, 4, 11, 0, tzinfo=IST)) is True   # Saturday


def test_entry_guard_resolves_intraday_charge_segment_to_cash_session():
    # the intraday branch passes the charge-segment ('NSE_INTRADAY'); it must map to
    # the 09:15-15:30 cash window, not silently allow everything.
    assert outside_trading_session("NSE_INTRADAY", dt.datetime(2026, 7, 3, 9, 1, tzinfo=IST)) is True
    assert outside_trading_session("NSE_INTRADAY", dt.datetime(2026, 7, 3, 11, 0, tzinfo=IST)) is False
    assert outside_trading_session("BSE_INTRADAY", dt.datetime(2026, 7, 3, 9, 1, tzinfo=IST)) is True


# ── #10 hard daily round-trip cap: halt new entries after N completed round trips ──
def test_round_trip_cap_not_reached():
    assert round_trip_cap_reached(8, 9) is False


def test_round_trip_cap_reached_at_cap():
    assert round_trip_cap_reached(9, 9) is True


def test_round_trip_cap_reached_over():
    assert round_trip_cap_reached(12, 9) is True


def test_round_trip_cap_disabled():
    assert round_trip_cap_reached(50, 0) is False


# ── #15 signal-age guard: a crossover is a LIVE event, not a standing order ──
# The bar epoch is the candle OPEN; the candle completes at bar + interval. A signal
# is actionable only within max_age minutes of that completion — after a restart the
# "latest completed candle" can be hours old (pre-open it is the PREVIOUS session's
# last bar), and entering there chases a move that already left (LODHA 2026-07-03:
# a prior-session crossover fired at 09:00, ~5% past its origin by noon).
def _epoch(y, mo, d, h, mi):
    from app.core.market_hours import ist_epoch
    return ist_epoch(dt.datetime(y, mo, d, h, mi))


def test_fresh_signal_within_age_passes():
    from app.engine.risk_controls import signal_too_old
    bar = _epoch(2026, 7, 3, 10, 30)                    # 15m candle completes 10:45
    assert signal_too_old(bar, _epoch(2026, 7, 3, 10, 46), 15, 5.0) is False


def test_signal_older_than_age_blocks():
    from app.engine.risk_controls import signal_too_old
    bar = _epoch(2026, 7, 3, 10, 30)                    # completes 10:45; now 12:00
    assert signal_too_old(bar, _epoch(2026, 7, 3, 12, 0), 15, 5.0) is True


def test_prior_session_bar_blocks_at_open():
    from app.engine.risk_controls import signal_too_old
    bar = _epoch(2026, 7, 2, 15, 15)                    # yesterday's last 15m candle
    assert signal_too_old(bar, _epoch(2026, 7, 3, 9, 31), 15, 5.0) is True


def test_signal_age_guard_disabled_when_zero():
    from app.engine.risk_controls import signal_too_old
    bar = _epoch(2026, 7, 2, 15, 15)
    assert signal_too_old(bar, _epoch(2026, 7, 3, 12, 0), 15, 0.0) is False


def test_signal_age_missing_bar_never_blocks():
    from app.engine.risk_controls import signal_too_old
    assert signal_too_old(None, _epoch(2026, 7, 3, 12, 0), 15, 5.0) is False


# ── #16b entry window: no NEW entry before the owner's start-of-day gate (09:30) ──
def test_entry_window_blocks_before_start():
    from app.engine.risk_controls import before_entry_window
    assert before_entry_window(dt.datetime(2026, 7, 3, 9, 20), "09:30") is True
    assert before_entry_window(dt.datetime(2026, 7, 3, 9, 29), "09:30") is True


def test_entry_window_allows_at_and_after_start():
    from app.engine.risk_controls import before_entry_window
    assert before_entry_window(dt.datetime(2026, 7, 3, 9, 30), "09:30") is False
    assert before_entry_window(dt.datetime(2026, 7, 3, 14, 0), "09:30") is False


def test_entry_window_blank_or_garbage_never_blocks():
    from app.engine.risk_controls import before_entry_window
    assert before_entry_window(dt.datetime(2026, 7, 3, 9, 0), "") is False
    assert before_entry_window(dt.datetime(2026, 7, 3, 9, 0), "banana") is False
