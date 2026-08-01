"""MTF carry cost — the thing that makes funded positions different.

Every other segment here is point-in-time: open, close, price difference net of
charges. MTF is not. The broker funds part of the position and charges interest
daily, so the cost changes while you do nothing — a trade profitable on Tuesday
can be a loss by Friday with the price unmoved.

Modelled wrong, the ledger slowly tells a story that never happened, and it does
so without any single moment where something looks obviously broken. That is why
MTF was scheduled last and behind E0.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.engine.carry import (DEFAULT_ANNUAL_RATE, accrued_to_date, carry_cost,
                              daily_interest, days_held, funded_amount)

MON = dt.date(2026, 8, 3)
FRI = dt.date(2026, 8, 7)


# ── what is actually funded ─────────────────────────────────────────────────

def test_interest_is_charged_on_the_funded_amount_not_the_position():
    """The broker lends the difference. Charging on the whole notional
    overstates the cost; charging on the margin inverts the relationship."""
    assert funded_amount(100_000.0, 25_000.0) == pytest.approx(75_000.0)


def test_over_collateralising_does_not_earn_interest():
    """A negative funded amount would appear in the ledger as a mysterious
    credit — money arriving from nowhere."""
    assert funded_amount(50_000.0, 80_000.0) == 0.0


def test_a_fully_paid_position_has_no_carry():
    assert carry_cost(position_value=100_000.0, margin_paid=100_000.0,
                      entry=MON, exit_=FRI) == 0.0


# ── the calendar ────────────────────────────────────────────────────────────

def test_interest_does_not_take_the_weekend_off():
    """Friday to Monday is THREE days of funding. A model counting trading days
    would understate every position held over a weekend — which is most of the
    ones MTF exists for."""
    fri, mon = dt.date(2026, 8, 7), dt.date(2026, 8, 10)
    assert days_held(fri, mon) == 4          # Fri, Sat, Sun, Mon


def test_a_same_day_close_still_costs_a_day():
    """The position WAS funded for a day. `exit - entry` would say zero."""
    assert days_held(MON, MON) == 1
    assert carry_cost(position_value=100_000.0, margin_paid=25_000.0,
                      entry=MON, exit_=MON) > 0


def test_an_impossible_range_is_zero_not_negative():
    assert days_held(FRI, MON) == 0


# ── the arithmetic ──────────────────────────────────────────────────────────

def test_one_days_interest_matches_the_annual_rate():
    expect = 75_000.0 * DEFAULT_ANNUAL_RATE / 365
    assert daily_interest(75_000.0) == pytest.approx(expect)


def test_cost_scales_linearly_with_days_held():
    """Simple, not compounded — brokers bill daily against the funded amount
    rather than rolling interest into the principal."""
    one = carry_cost(position_value=100_000.0, margin_paid=25_000.0, entry=MON, exit_=MON)
    five = carry_cost(position_value=100_000.0, margin_paid=25_000.0, entry=MON, exit_=FRI)
    # Tolerance is one paisa, not 1e-6: the TOTAL is rounded once, which is what
    # a broker actually bills. Rounding each day and summing would drift, so
    # `5 x round(day)` is legitimately a paisa off `round(5 x day)`.
    assert five == pytest.approx(one * 5, abs=0.05)


def test_the_cost_is_returned_positive():
    """It is a COST and the caller subtracts it. Returning a negative would
    invite a sign error exactly where a sign error is least visible."""
    assert carry_cost(position_value=100_000.0, margin_paid=25_000.0,
                      entry=MON, exit_=FRI) > 0


def test_a_zero_rate_means_no_carry():
    assert carry_cost(position_value=100_000.0, margin_paid=25_000.0,
                      entry=MON, exit_=FRI, annual_rate=0.0) == 0.0


# ── the open position ───────────────────────────────────────────────────────

def test_an_open_position_accrues_every_day_it_is_held():
    """Unrealized P&L must include this, or a held position looks BETTER each
    day — the exact opposite of the truth, compounding silently for as long as
    it stays open."""
    d1 = accrued_to_date(position_value=100_000.0, margin_paid=25_000.0,
                         entry=MON, today=MON)
    d5 = accrued_to_date(position_value=100_000.0, margin_paid=25_000.0,
                         entry=MON, today=FRI)
    assert d5 > d1 > 0


def test_a_realistic_hold_costs_a_real_amount():
    """Sanity on the magnitude: ₹75,000 funded for a month at ~15% is roughly
    ₹925. Small enough to ignore per day, large enough to erase a thin edge over
    a month — which is precisely why it must be in the P&L rather than a
    footnote."""
    cost = carry_cost(position_value=100_000.0, margin_paid=25_000.0,
                      entry=MON, exit_=MON + dt.timedelta(days=29))
    assert 800 < cost < 1_100, f"got ₹{cost}"


# ── a funded position is not a forever position ─────────────────────────────

def test_a_position_within_its_cap_is_not_expired():
    from app.engine.carry import holding_expired
    assert holding_expired(MON, MON + dt.timedelta(days=10), 30) is False


def test_a_position_past_its_cap_is_expired():
    """Interest accrues every calendar day whether or not anyone is watching.
    MTF is the only segment where a forgotten position bleeds money indefinitely,
    so the cap is the backstop against simply not noticing."""
    from app.engine.carry import holding_expired
    assert holding_expired(MON, MON + dt.timedelta(days=31), 30) is True


def test_the_cap_uses_the_same_inclusive_day_count_as_the_billing():
    """If the cap and the interest disagreed about what a day is, a position
    could be billed for a day it was not allowed to be held."""
    from app.engine.carry import days_held, holding_expired
    assert days_held(MON, MON + dt.timedelta(days=29)) == 30
    assert holding_expired(MON, MON + dt.timedelta(days=29), 30) is False
    assert holding_expired(MON, MON + dt.timedelta(days=30), 30) is True


def test_a_zero_cap_means_no_cap():
    """Deliberate, not an oversight: the owner may want an indefinite hold, and
    a hard-coded ceiling would be this module deciding a lifecycle question it
    has no business deciding."""
    from app.engine.carry import holding_expired
    assert holding_expired(MON, MON + dt.timedelta(days=9999), 0) is False
