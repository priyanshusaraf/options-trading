"""The index-futures segment ships COMPLETE and OFF.

E2 adds a new leveraged segment to a system that trades real money. The spec's
own build plan makes owner review step 13 — after everything is built and before
the flag ever flips outside a test. So the guarantee these tests pin is not
"futures work", it is "futures cannot happen by accident": with the flag at its
default, no code path can produce a futures candidate, and no deploy can turn it
on without someone deciding to.
"""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.engine.charges import ChargeScheduleRefusal, compute_charges


def _defaults() -> Settings:
    return Settings(_env_file=None)


def test_the_segment_is_off_by_default():
    assert _defaults().index_futures_enabled is False


def test_the_delivery_guard_is_on_by_default():
    """The guard defaults ON even though it is a no-op for cash-settled index
    futures — so a commodity extension inherits protection rather than having to
    remember to ask for it."""
    assert _defaults().index_futures_delivery_guard is True


def test_sizing_knobs_are_present_and_sane():
    s = _defaults()
    assert s.index_futures_max_margin > s.index_futures_min_margin > 0
    assert 0 < s.index_futures_margin_pct < 1
    assert 0 < s.index_futures_stop_loss_pct < s.index_futures_target_pct


def test_concurrency_starts_at_one():
    """A new leveraged segment starts with a single position. Widening it is a
    decision; inheriting 4 from the equity segment would not be."""
    assert _defaults().index_futures_max_positions == 1


# ── charges ─────────────────────────────────────────────────────────────────

def test_bfo_fut_charges_exist():
    """SENSEX futures had no charge schedule at all; a P&L computed without one
    would silently book a trade as free."""
    out = compute_charges("BFO_FUT", "BUY", 80_000.0, 10)
    assert out["total"] > 0


def test_futures_charges_are_direction_aware():
    """STT/CTT is a SELL-side tax. Charging it on both legs, or neither, is the
    class of error that made equity SHORT P&L wrong (safety item E7)."""
    buy = compute_charges("NFO_FUT", "BUY", 24_000.0, 50)
    sell = compute_charges("NFO_FUT", "SELL", 24_000.0, 50)
    assert sell["total"] > buy["total"]


def test_bfo_is_not_cheaper_than_nfo_by_accident():
    """BSE's derivatives transaction charge is unverified against a contract
    note, so it is deliberately set equal to NSE's — the model must never
    UNDER-charge, because an optimistic cost model flatters every result built
    on it."""
    nfo = compute_charges("NFO_FUT", "SELL", 50_000.0, 20)["total"]
    bfo = compute_charges("BFO_FUT", "SELL", 50_000.0, 20)["total"]
    assert bfo >= nfo


def test_an_unknown_segment_does_not_silently_cost_zero():
    """A typo'd segment name must not read as a free trade."""
    known = compute_charges("NFO_FUT", "BUY", 24_000.0, 50)["total"]
    assert known > 0
    with pytest.raises(ChargeScheduleRefusal, match="unknown segment"):
        compute_charges("TYPO_FUT", "BUY", 24_000.0, 50)


def test_the_margin_target_can_actually_buy_one_lot():
    """A default too small for a single lot would make the segment look BROKEN
    rather than off — it would silently never trade, which is a worse failure
    than either state. One NIFTY lot is ~₹18 lakh of notional, so at the 12%
    estimate it blocks ~₹2.1 lakh."""
    s = _defaults()
    one_lot_margin = 24_000.0 * 75 * s.index_futures_margin_pct
    assert s.index_futures_max_margin >= one_lot_margin, (
        f"₹{s.index_futures_max_margin:,.0f} target cannot fund one lot "
        f"(~₹{one_lot_margin:,.0f})")
    assert s.index_futures_max_margin < 2 * one_lot_margin, \
        "the default should reach one lot, not two"
