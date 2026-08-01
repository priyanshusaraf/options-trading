"""Event-risk blackouts — one rule table, consulted identically by the live engine, the
backtester and the UI.

Owner's rule (2026-08-01): "whenever there is event-specific risk for any instrument we
don't wanna trade it, because it invites too much risk." Concretely:

  • NATURALGAS  — Thursdays around the EIA natural-gas storage report
  • CRUDEOIL/M  — Wednesdays around the EIA petroleum status report
                  (both are 10:30 US/Eastern, so the IST window MOVES with US daylight
                  saving: 20:00 IST in summer, 21:00 IST in winter — never hardcode it)
  • NIFTY       — no options on Tuesdays
  • SENSEX      — no trading on Thursdays
  • BANKNIFTY   — no trading on Wednesdays
  • GOLDM/SILVERM — no options within 2 days of expiry
  • any stock   — nothing on its earnings date

These gate ENTRIES ONLY. Exits are never gated by anything (hard invariant #2: not getting
out is worse than any other failure).
"""
import datetime as dt

import pytest

from app.engine.event_risk import (
    DEFAULT_RULES,
    active_blackout,
    blackouts_for_day,
    event_window_ist,
)


def ist(y, m, d, hh=10, mm=0):
    return dt.datetime(y, m, d, hh, mm)


# ── DST-correct US report windows ────────────────────────────────────────────

def test_us_report_window_is_20_00_ist_during_us_summer_time():
    """2026-08-06 is a Thursday in US EDT: 10:30 ET == 20:00 IST, so the owner's stated
    19:30–20:01 IST window."""
    start, end = event_window_ist(dt.date(2026, 8, 6), "10:30", before_minutes=30,
                                  after_minutes=1)
    assert (start.hour, start.minute) == (19, 30)
    assert (end.hour, end.minute) == (20, 1)


def test_us_report_window_shifts_to_21_00_ist_in_us_winter():
    """2026-01-08 is a Thursday in US EST: 10:30 ET == 21:00 IST. A hardcoded 19:30–20:01
    would leave the bot trading straight through the release for four months a year."""
    start, end = event_window_ist(dt.date(2026, 1, 8), "10:30", before_minutes=30,
                                  after_minutes=1)
    assert (start.hour, start.minute) == (20, 30)
    assert (end.hour, end.minute) == (21, 1)


# ── NATURALGAS: Thursday EIA gas storage ─────────────────────────────────────

@pytest.mark.parametrize("key", ["NATURALGAS", "NATGAS"])
def test_natgas_blocked_inside_the_thursday_window(key):
    b = active_blackout(key, "options", ist(2026, 8, 6, 19, 45))
    assert b is not None
    assert "natural-gas" in b.label.lower()


def test_natgas_tradable_before_and_after_the_window():
    assert active_blackout("NATURALGAS", "options", ist(2026, 8, 6, 19, 29)) is None
    assert active_blackout("NATURALGAS", "options", ist(2026, 8, 6, 20, 2)) is None


def test_natgas_unaffected_on_other_weekdays():
    assert active_blackout("NATURALGAS", "options", ist(2026, 8, 5, 19, 45)) is None


def test_natgas_window_applies_to_every_product_not_just_options():
    assert active_blackout("NATURALGAS", "equity_intraday", ist(2026, 8, 6, 19, 45))
    assert active_blackout("NATURALGAS", "futures", ist(2026, 8, 6, 19, 45))


# ── CRUDEOIL / CRUDEOILM: Wednesday EIA petroleum status ─────────────────────

@pytest.mark.parametrize("key", ["CRUDEOIL", "CRUDEOILM"])
def test_crude_blocked_inside_the_wednesday_window(key):
    b = active_blackout(key, "options", ist(2026, 8, 5, 19, 45))
    assert b is not None
    assert "petroleum" in b.label.lower() or "crude" in b.label.lower()


def test_crude_not_blocked_on_thursday():
    assert active_blackout("CRUDEOIL", "options", ist(2026, 8, 6, 19, 45)) is None


def test_crude_winter_window_moves_with_dst():
    """2026-01-07 is a Wednesday in EST — 19:45 IST is now BEFORE the window."""
    assert active_blackout("CRUDEOIL", "options", ist(2026, 1, 7, 19, 45)) is None
    assert active_blackout("CRUDEOIL", "options", ist(2026, 1, 7, 20, 45)) is not None


# ── index weekday rules ──────────────────────────────────────────────────────

def test_nifty_options_blocked_all_tuesday():
    for hh in (9, 12, 15):
        assert active_blackout("NIFTY", "options", ist(2026, 8, 4, hh)) is not None
    assert active_blackout("NIFTY", "options", ist(2026, 8, 5, 12)) is None


def test_nifty_tuesday_rule_does_not_leak_onto_other_instruments():
    """A NIFTY expiry says nothing about SUZLON — this is the 2026-07-28 lesson, kept."""
    assert active_blackout("SUZLON", "equity_intraday", ist(2026, 8, 4, 12)) is None
    assert active_blackout("BANKNIFTY", "options", ist(2026, 8, 4, 12)) is None


def test_sensex_blocked_all_thursday():
    assert active_blackout("SENSEX", "options", ist(2026, 8, 6, 12)) is not None
    assert active_blackout("SENSEX", "options", ist(2026, 8, 5, 12)) is None


def test_banknifty_blocked_all_wednesday():
    assert active_blackout("BANKNIFTY", "options", ist(2026, 8, 5, 12)) is not None
    assert active_blackout("BANKNIFTY", "options", ist(2026, 8, 6, 12)) is None


# ── GOLDM / SILVERM: no options into expiry ──────────────────────────────────

@pytest.mark.parametrize("key", ["GOLDM", "SILVERM"])
@pytest.mark.parametrize("days_out", [0, 1, 2])
def test_bullion_options_blocked_within_two_days_of_expiry(key, days_out):
    day = ist(2026, 8, 10, 12)
    expiry = day.date() + dt.timedelta(days=days_out)
    assert active_blackout(key, "options", day, expiry=expiry) is not None


def test_bullion_options_tradable_three_days_out():
    day = ist(2026, 8, 10, 12)
    assert active_blackout("GOLDM", "options", day,
                           expiry=day.date() + dt.timedelta(days=3)) is None


def test_bullion_expiry_rule_is_options_only():
    """The rule the owner gave is about option decay into expiry, not the underlying."""
    day = ist(2026, 8, 10, 12)
    assert active_blackout("GOLDM", "futures", day,
                           expiry=day.date() + dt.timedelta(days=1)) is None


def test_bullion_with_unknown_expiry_is_not_blocked():
    """No expiry supplied (equity paths never have one) must not blanket-block."""
    assert active_blackout("GOLDM", "options", ist(2026, 8, 10, 12), expiry=None) is None


# ── earnings ─────────────────────────────────────────────────────────────────

def test_stock_blocked_on_its_earnings_date():
    day = ist(2026, 8, 5, 11)
    b = active_blackout("INFY", "equity_intraday", day, earnings_date=day.date())
    assert b is not None
    assert "earnings" in b.label.lower()


def test_stock_tradable_the_day_after_earnings():
    day = ist(2026, 8, 5, 11)
    assert active_blackout("INFY", "equity_intraday", day,
                           earnings_date=day.date() - dt.timedelta(days=1)) is None


def test_earnings_rule_applies_to_any_symbol_not_a_fixed_list():
    day = ist(2026, 8, 5, 11)
    assert active_blackout("SOMETHINGNEW", "equity_intraday", day,
                           earnings_date=day.date()) is not None


# ── switches, introspection, safety ──────────────────────────────────────────

def test_everything_can_be_switched_off_globally():
    assert active_blackout("SENSEX", "options", ist(2026, 8, 6, 12), enabled=False) is None


def test_blackouts_for_day_lists_the_days_rules_for_the_ui():
    """The cockpit must be able to say WHY an instrument is sitting out, in advance."""
    out = blackouts_for_day("NATURALGAS", "options", dt.date(2026, 8, 6))
    assert len(out) == 1
    assert out[0].window is not None
    assert out[0].window[0].strftime("%H:%M") == "19:30"

    assert blackouts_for_day("SENSEX", "options", dt.date(2026, 8, 6))[0].window is None
    assert blackouts_for_day("SENSEX", "options", dt.date(2026, 8, 5)) == []


def test_rules_are_matched_case_insensitively_and_by_exchange_prefix():
    """Keys reach the engine as 'NSE:INFY', 'NIFTY', 'naturalgas' depending on the path.
    A rule that silently stops matching because of a prefix is a safety hole."""
    assert active_blackout("nse:sensex", "options", ist(2026, 8, 6, 12)) is not None
    assert active_blackout("MCX:NATURALGAS", "options", ist(2026, 8, 6, 19, 45)) is not None


def test_every_default_rule_is_documented_and_well_formed():
    """A rule with no human-readable label would show up in the UI as a blank reason."""
    for r in DEFAULT_RULES:
        assert r.label and len(r.label) > 8, r
        # Only the earnings rule may be keyless (it matches any symbol, driven by the
        # calendar). Any OTHER keyless rule would silently blanket-block the whole book.
        assert r.keys or r.kind == "earnings", r
        assert r.products, r
        assert r.kind in ("us_report", "weekday", "pre_expiry", "earnings"), r
