"""Futures P&L and equity contribution — and proof the other segments moved not at all.

`index_futures` is margined and short-capable, exactly like `equity_intraday`:
only the margin leaves cash, so the position contributes margin + unrealized P&L
to portfolio equity. Contributing its full notional instead would double-count
the leverage and inflate equity on every tick — the same class of error the
`mtm_value` docstring already warns about for MIS.

Half of this file exists to prove the OPTIONS and EQUITY paths are byte-identical
after the change. Widening a segment set is exactly the kind of edit that
silently re-prices an untouched segment.
"""
from __future__ import annotations

import pytest

from app.db.models import MARGIN_SEGMENTS, Position


def _pos(segment, direction, entry, last, qty=50, entry_cost=25_000.0):
    return Position(owner_id='owner', broker_account_id='account.default', instrument_key="NIFTY", segment=segment, direction=direction,
                    entry_premium=entry, last_premium=last, qty=qty,
                    entry_cost=entry_cost, tradingsymbol="NIFTYFUT")


# ── futures ─────────────────────────────────────────────────────────────────

def test_a_long_future_profits_when_price_rises():
    assert _pos("index_futures", "LONG", 24_000.0, 24_100.0).unrealized_pnl() == \
        pytest.approx(100.0 * 50)


def test_a_short_future_profits_when_price_falls():
    """Futures short properly — unlike the long-premium options path. Getting
    this wrong inverts the sign on every short position (safety item E8)."""
    assert _pos("index_futures", "SHORT", 24_000.0, 23_900.0).unrealized_pnl() == \
        pytest.approx(100.0 * 50)


def test_a_short_future_loses_when_price_rises():
    assert _pos("index_futures", "SHORT", 24_000.0, 24_100.0).unrealized_pnl() == \
        pytest.approx(-100.0 * 50)


def test_futures_contribute_margin_plus_pnl_not_notional():
    """The one that would inflate the whole book. A NIFTY future at 24,000 x 50
    is ₹1.2 CRORE of notional against ~₹25k of margin: returning notional here
    would report an account ~48x its real size."""
    p = _pos("index_futures", "LONG", 24_000.0, 24_100.0, entry_cost=25_000.0)
    assert p.mtm_value() == pytest.approx(25_000.0 + 5_000.0)
    assert p.mtm_value() < 1_000_000, "notional leaked into portfolio equity"


# ── the segments that must NOT have moved ───────────────────────────────────

def test_options_still_contribute_full_liquidation_value():
    """Options are fully paid for — the whole premium left cash, so the position
    is worth premium x qty, not margin + P&L."""
    p = _pos("options", "LONG", 100.0, 160.0, qty=75, entry_cost=7_500.0)
    assert p.mtm_value() == pytest.approx(160.0 * 75)


def test_options_short_is_still_treated_as_long_premium():
    """The options path is always long-premium; a 'SHORT' there means a bought
    PUT, not a sold contract. This must not have picked up short semantics."""
    p = _pos("options", "SHORT", 100.0, 160.0, qty=75)
    assert p.unrealized_pnl() == pytest.approx(60.0 * 75)


def test_equity_intraday_is_unchanged_long_and_short():
    long_ = _pos("equity_intraday", "LONG", 500.0, 510.0, qty=100, entry_cost=10_000.0)
    short = _pos("equity_intraday", "SHORT", 500.0, 490.0, qty=100, entry_cost=10_000.0)
    assert long_.unrealized_pnl() == pytest.approx(1_000.0)
    assert short.unrealized_pnl() == pytest.approx(1_000.0)
    assert long_.mtm_value() == pytest.approx(11_000.0)


# ── the set itself ──────────────────────────────────────────────────────────

def test_both_methods_agree_on_which_segments_are_leveraged():
    """A named set, not a repeated literal: one method saying 'futures are
    margined' while the other says 'fully paid' would inflate equity by the
    notional on every futures tick."""
    assert MARGIN_SEGMENTS == {"equity_intraday", "index_futures"}
    assert "options" not in MARGIN_SEGMENTS


def test_an_unmarked_position_does_not_crash():
    p = _pos("index_futures", "LONG", 24_000.0, None)
    assert p.unrealized_pnl() == 0.0
