"""E7 — equity charge legs must follow the DIRECTION, not a hardcoded BUY/SELL.

An equity-intraday SHORT is SELL-to-open / BUY-to-cover, but the broker charged the
entry as a BUY and the exit as a SELL regardless of direction. On NSE_INTRADAY that
puts STT (0.025%, sell-side) on the wrong leg and stamp duty (0.003%, buy-side) on the
wrong leg, so `Trade.net_pnl` can't reconcile against the real contract note on shorts.
It is self-consistent, so `reconcile()` never flagged it. `live_broker.py` already
gets this right — the paper broker is the outlier.
"""

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.charges import compute_charges
from app.engine.runner import EngineRunner

SEG = "NSE_INTRADAY"
ENTRY, EXIT, QTY = 100.0, 95.0, 10


def _short():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    pos = r.broker.open_equity_position(get_instrument("NIFTY"), "SHORT", ENTRY, QTY,
                                        SEG, "t", r.provider.now(), params={})
    return r, pos


def test_short_entry_leg_is_charged_as_a_sell():
    r, pos = _short()
    expected = compute_charges(SEG, "SELL", ENTRY, QTY)["total"]
    assert pos.entry_charges == expected, (
        f"a SHORT opens by SELLING: entry charges {pos.entry_charges} should be the "
        f"SELL leg {expected}, not the BUY leg "
        f"{compute_charges(SEG, 'BUY', ENTRY, QTY)['total']}")


def test_short_round_trip_charges_match_the_real_order_sequence():
    r, pos = _short()
    tr = r.broker.close_equity_position(pos, EXIT, "TARGET", r.provider.now())
    expected = (compute_charges(SEG, "SELL", ENTRY, QTY)["total"]      # sell to open
                + compute_charges(SEG, "BUY", EXIT, QTY)["total"])     # buy to cover
    assert tr.charges_total == round(expected, 2), (
        f"short round-trip charges {tr.charges_total} != contract-note basis {expected}")


def test_long_legs_are_unchanged():
    """A LONG is BUY-to-open / SELL-to-close — the existing behaviour, pinned."""
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    pos = r.broker.open_equity_position(get_instrument("NIFTY"), "LONG", ENTRY, QTY,
                                        SEG, "t", r.provider.now(), params={})
    assert pos.entry_charges == compute_charges(SEG, "BUY", ENTRY, QTY)["total"]
    tr = r.broker.close_equity_position(pos, EXIT, "STOP_LOSS", r.provider.now())
    expected = (compute_charges(SEG, "BUY", ENTRY, QTY)["total"]
                + compute_charges(SEG, "SELL", EXIT, QTY)["total"])
    assert tr.charges_total == round(expected, 2)


def test_short_partial_close_covers_with_a_buy_leg():
    r, pos = _short()
    tr = r.broker.book_partial_close_equity(pos, 4, EXIT, "PARTIAL", r.provider.now())
    exit_leg = compute_charges(SEG, "BUY", EXIT, 4)["total"]
    entry_slice = compute_charges(SEG, "SELL", ENTRY, QTY)["total"] * 4 / QTY
    # (this path stores charges_total unrounded, unlike the full-close path)
    assert tr.charges_total == pytest.approx(entry_slice + exit_leg), (
        f"partial cover of a short charged the wrong legs: {tr.charges_total}")


def test_ledger_stays_exact_for_a_short_round_trip():
    """Whatever the legs, the cash invariant must not drift."""
    r, pos = _short()
    r.broker.close_equity_position(pos, EXIT, "TARGET", r.provider.now())
    assert r.broker.reconcile()["diff"] == 0.0
