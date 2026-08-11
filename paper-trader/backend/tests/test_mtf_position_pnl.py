"""A funded position's P&L worsens while nothing happens.

MTF is the only segment here whose value is TIME-DEPENDENT. The broker lends
part of the position and charges interest daily, so unrealized P&L must include
accrued carry — otherwise a held position looks better every day it is held,
which is the exact opposite of the truth, and the error compounds silently for
as long as it stays open. For MTF that can be weeks.

Half this file proves the OTHER segments did not move. Adding a time-dependent
term to a shared P&L method is exactly the change that silently re-prices
everything else.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.db.models import FUNDED_SEGMENTS, MARGIN_SEGMENTS, Position

ENTRY = dt.datetime(2026, 8, 3, 10, 0)


def _pos(segment, *, entry=500.0, last=None, qty=200, days=0,
         entry_cost=25_000.0, entry_charges=0.0, direction="LONG"):
    return Position(owner_id='owner', broker_account_id='account.default',
        instrument_key="X", segment=segment, direction=direction,
        entry_premium=entry, last_premium=(entry if last is None else last),
        qty=qty, entry_cost=entry_cost, entry_charges=entry_charges,
        entry_time=ENTRY, last_mark_time=ENTRY + dt.timedelta(days=days),
        tradingsymbol="X")


# ── the funded segment ──────────────────────────────────────────────────────

def test_a_funded_position_loses_money_while_the_price_does_not_move():
    """The defining property. Same price in and out, held a month, and the
    position is DOWN — because it was funded the whole time."""
    flat_today = _pos("mtf", days=0)
    flat_month = _pos("mtf", days=30)
    assert flat_month.unrealized_pnl() < flat_today.unrealized_pnl()
    assert flat_month.unrealized_pnl() < 0


def test_carry_grows_with_time_held():
    a = _pos("mtf", days=1).accrued_carry()
    b = _pos("mtf", days=20).accrued_carry()
    assert 0 < a < b


def test_carry_is_charged_on_the_funded_amount_not_the_notional():
    """₹100k position with ₹25k margin is ₹75k funded. Charging on the notional
    would overstate the cost by a third."""
    lightly_funded = _pos("mtf", entry_cost=90_000.0, days=30)   # only ₹10k lent
    heavily_funded = _pos("mtf", entry_cost=10_000.0, days=30)   # ₹90k lent
    assert heavily_funded.accrued_carry() > lightly_funded.accrued_carry()


def test_a_profitable_move_still_nets_off_the_carry():
    p = _pos("mtf", entry=500.0, last=520.0, qty=200, days=30)
    gross = (520.0 - 500.0) * 200
    assert p.unrealized_pnl() < gross
    assert p.unrealized_pnl() == pytest.approx(gross - p.accrued_carry())


def test_carry_never_raises_on_a_malformed_row():
    """A carry figure that cannot be computed must not take down the mark loop —
    that loop fires stops on every other position in the book.

    A row with no `entry_cost` has no known margin, so the funded amount reads as
    the whole position and carry comes out HIGH rather than zero. That is the
    conservative direction and the intended one: over-stating a cost is safe,
    under-stating it flatters the position. The contract asserted here is
    therefore "never raises, always a sane number" — not "zero"."""
    broken = Position(owner_id='owner', broker_account_id='account.default', instrument_key="X", segment="mtf", direction="LONG",
                      entry_premium=100.0, last_premium=100.0, qty=10,
                      entry_cost=None, entry_time=None, last_mark_time=None)
    carry = broken.accrued_carry()
    assert carry >= 0.0
    assert carry < 100.0, "a malformed row produced an absurd carry"
    broken.unrealized_pnl()      # must not raise


# ── the segments that must NOT have moved ───────────────────────────────────

@pytest.mark.parametrize("segment", ["options", "equity_intraday", "index_futures"])
def test_no_other_segment_accrues_carry(segment):
    """Only MTF is funded. Giving futures or MIS a daily interest charge would
    quietly erode every intraday result."""
    assert _pos(segment, days=30).accrued_carry() == 0.0


@pytest.mark.parametrize("segment", ["options", "equity_intraday", "index_futures"])
def test_time_alone_does_not_change_other_segments(segment):
    """A held options position is worth what it is worth — holding it is free."""
    assert _pos(segment, days=0).unrealized_pnl() == \
        _pos(segment, days=30).unrealized_pnl()


def test_equity_short_math_is_unchanged():
    short = _pos("equity_intraday", entry=500.0, last=490.0, direction="SHORT")
    assert short.unrealized_pnl() == pytest.approx(10.0 * 200)


def test_options_long_premium_math_is_unchanged():
    p = _pos("options", entry=100.0, last=160.0, qty=75)
    assert p.unrealized_pnl() == pytest.approx(60.0 * 75)


# ── the sets are distinct on purpose ────────────────────────────────────────

def test_funded_and_margined_are_different_ideas():
    """Both are leveraged, but 'only the margin left cash' and 'interest accrues
    daily' are different facts. One set conflating them would give futures a
    carry cost or MTF an intraday square-off."""
    assert FUNDED_SEGMENTS == {"mtf"}
    assert not (FUNDED_SEGMENTS & MARGIN_SEGMENTS)


def test_the_segment_is_off_by_default():
    from app.core.config import Settings
    assert Settings(_env_file=None).mtf_enabled is False


# ── MTF must never be caught by the intraday force-flat ─────────────────────

def test_mtf_is_excluded_from_the_intraday_squareoff():
    """The invariant that makes MTF possible at all.

    `square_off_intraday` flattens equity_intraday and index_futures near the
    close. If MTF were ever caught by it, every funded position would be
    liquidated the day it was opened — destroying the entire point of a
    multi-day segment, while looking like normal end-of-day housekeeping.

    Asserted against the source because it is an ABSENCE, and absences are what
    refactors delete: someone widening that filter to 'all leveraged segments'
    would break this without touching anything named mtf."""
    import inspect
    from app.engine.runner import EngineRunner
    src = inspect.getsource(EngineRunner.square_off_intraday)
    assert '"equity_intraday", "index_futures"' in src
    assert "mtf" not in src, (
        "MTF reached the intraday force-flat — funded positions would be "
        "liquidated the day they are opened")
