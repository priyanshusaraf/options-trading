"""Intraday-equity sizing + the contention selector — the heart of the new risk
logic, so it's pinned hard and in isolation (pure functions, no engine/DB).

Owner's rules, exactly:
  * size by MARGIN deployed (7–10k) × 5x leverage → qty = floor(margin×lev/price)
  * HARD cap of 3 concurrent trades TOTAL (purple included)
  * purple priority names always win selection, sized at purple_margin
  * non-purple compete for leftover slots by HIGHER QUANTITY (cheaper share)
  * cash-greedy; below the min-margin floor or unaffordable → skipped
"""
import pytest

from app.engine.equity_entry import (
    IntradayCandidate, equity_qty, select_intraday_entries)

LEV = 5.0
SEL = dict(max_positions=3, min_margin=7_000.0, max_margin=10_000.0,
           purple_margin=10_000.0, leverage=LEV, available_cash=1_000_000.0)


def _c(key, price, purple=False, direction="LONG"):
    return IntradayCandidate(key, direction, price, purple)


def test_equity_qty_is_margin_times_leverage_over_price():
    assert equity_qty(10_000, 5, 250) == 200      # 50,000 / 250
    assert equity_qty(7_000, 5, 100) == 350        # 35,000 / 100
    assert equity_qty(10_000, 5, 0) == 0           # guard
    assert equity_qty(0, 5, 100) == 0


def test_cheapest_share_wins_under_contention():
    # 4 names, cap 3, ample cash → the 3 with the HIGHEST qty (cheapest shares)
    cands = [_c("A", 100), _c("B", 1_000), _c("C", 5_000), _c("D", 250)]
    res = select_intraday_entries(cands, **SEL)
    keys = {p.instrument_key for p in res.selected}
    assert len(res.selected) == 3
    assert keys == {"A", "D", "B"}                 # 5000 (fewest shares) dropped
    assert any(c.instrument_key == "C" for c, _ in res.skipped)


def test_hard_cap_of_three_total():
    cands = [_c(k, 100 + i) for i, k in enumerate(["A", "B", "C", "D", "E"])]
    res = select_intraday_entries(cands, **SEL)
    assert len(res.selected) == 3


def test_purple_always_selected_and_counts_toward_cap():
    # purple is expensive (fewest shares) yet MUST be taken; it occupies one of the
    # 3 slots, so only the 2 cheapest non-purple join it.
    cands = [_c("PURP", 5_000, purple=True), _c("A", 100), _c("B", 200), _c("C", 300)]
    res = select_intraday_entries(cands, **SEL)
    keys = [p.instrument_key for p in res.selected]
    assert "PURP" in keys
    assert len(res.selected) == 3
    assert set(keys) == {"PURP", "A", "B"}         # C dropped by the cap
    assert any(c.instrument_key == "C" for c, _ in res.skipped)


def test_purple_sized_at_purple_margin():
    res = select_intraday_entries([_c("PURP", 100, purple=True)],
                                  **{**SEL, "purple_margin": 10_000.0})
    p = res.selected[0]
    assert p.qty == equity_qty(10_000, LEV, 100)   # 500
    assert p.margin == pytest.approx(p.qty * 100 / LEV)


def test_cash_shortfall_skips_by_selection_order():
    # only ~10k cash → exactly one ~10k-margin pick funds, the rest skip
    cands = [_c("A", 100), _c("B", 200), _c("C", 300)]
    res = select_intraday_entries(cands, **{**SEL, "available_cash": 10_000.0})
    assert len(res.selected) == 1
    assert res.selected[0].instrument_key == "A"   # cheapest/highest-qty wins the cash
    assert sum(p.margin for p in res.selected) <= 10_000.0 + 1e-6


def test_too_expensive_for_one_share_is_skipped():
    # at 10k margin × 5x = 50k buying power, a 60k share buys 0 shares
    res = select_intraday_entries([_c("RICH", 60_000)], **SEL)
    assert not res.selected
    assert res.skipped and res.skipped[0][0].instrument_key == "RICH"


def test_below_min_margin_floor_is_skipped():
    # 30k share: 1 share = 30k notional = 6k margin (<7k floor) → skipped
    res = select_intraday_entries([_c("MID", 30_000)], **SEL)
    assert not res.selected
    assert any("floor" in reason.lower() for _, reason in res.skipped)


def test_margin_used_never_exceeds_target():
    res = select_intraday_entries([_c("A", 333)], **SEL)
    p = res.selected[0]
    assert p.margin <= 10_000.0 + 1e-6
    assert p.qty == equity_qty(10_000, LEV, 333)


# ── entry cutoff near the square-off boundary (2026-07-15 NCC 1-second-trade bug):
# an intraday entry with only seconds left before force-flat pays entry+exit
# charges/spread for a position that never gets a chance to work. Guard: skip any
# candidate whose instrument is inside `entry_cutoff_minutes` of session close. ──

def test_candidate_inside_cutoff_window_is_skipped_with_reason():
    # NCC-style repro: signal fires 1 minute before close, cutoff is 25m.
    res = select_intraday_entries(
        [_c("NCC", 100)], **{**SEL, "minutes_to_close": {"NCC": 1.0},
                             "entry_cutoff_minutes": 25.0})
    assert not res.selected
    assert res.skipped and res.skipped[0][0].instrument_key == "NCC"
    assert "entry_cutoff" in res.skipped[0][1]


def test_candidate_just_outside_cutoff_window_still_enters():
    # 25.01m to close, cutoff 25.0m → just outside the blocked window, enters normally.
    res = select_intraday_entries(
        [_c("A", 100)], **{**SEL, "minutes_to_close": {"A": 25.01},
                           "entry_cutoff_minutes": 25.0})
    assert len(res.selected) == 1
    assert res.selected[0].instrument_key == "A"


def test_cutoff_guard_is_a_noop_without_minutes_to_close_data():
    # Backward-compatible default: callers that don't pass minutes_to_close (or
    # pass 0 cutoff) get the pre-existing selection behaviour unchanged.
    res = select_intraday_entries([_c("A", 100)], **SEL)
    assert len(res.selected) == 1


def test_default_entry_cutoff_exceeds_square_off_buffer():
    # A new intraday position must always have headroom to work before the
    # force-flat fires, so the entry cutoff must be strictly later (in
    # minutes-before-close terms, a LARGER number) than the square-off buffer.
    from app.core.config import Settings
    s = Settings()
    assert s.intraday_entry_cutoff_minutes > s.intraday_square_off_buffer_minutes
    assert s.intraday_entry_cutoff_minutes == pytest.approx(
        s.intraday_square_off_buffer_minutes + 10.0)
