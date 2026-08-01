"""Carry cost for funded (MTF) positions — the thing that makes MTF P&L different.

Every other segment this engine trades is point-in-time: you open, you close,
P&L is a price difference net of two legs' charges. MTF is not. The broker funds
part of the position and charges interest for every day you hold it, so a
position's cost changes while you do nothing, and a trade that was profitable on
Tuesday can be a loss by Friday without the price moving at all.

That is the whole reason MTF was scheduled last and behind E0 (P&L integrity):
carry has to be modelled correctly or the ledger slowly tells a story that never
happened.

Three decisions, all of which are easy to get subtly wrong:

**Interest accrues on the FUNDED amount, not the position value.** The broker
lends the difference between the position's value and your margin. Charging
interest on the whole notional overstates the cost; charging it on the margin
inverts the relationship entirely.

**Calendar days, not trading days.** Interest does not take the weekend off. A
Friday-to-Monday hold is three days of funding, and a model that counted one
would understate every position held over a weekend — which is most of them.

**Day count is INCLUSIVE of the open date.** Zerodha and every MTF provider
charge from the day the position is funded. Counting `exit - entry` gives zero
for a same-day close that was, in fact, funded for a day.
"""
from __future__ import annotations

import datetime as dt

# Zerodha's published MTF interest rate. Annual, charged daily on the funded
# amount. RATE UNVERIFIED against a real statement — treat the number as a
# starting point and confirm before trusting an MTF P&L to the rupee. It is set
# high rather than low on purpose: a cost model that under-charges flatters every
# position built on it.
DEFAULT_ANNUAL_RATE = 0.1499        # ~14.99% p.a.
DAYS_IN_YEAR = 365                  # calendar basis, matching how brokers bill


def funded_amount(position_value: float, margin_paid: float) -> float:
    """What the broker actually lent: position value minus your own margin.

    Never negative — over-collateralising does not earn you interest, and a
    negative funded amount would show up as a mysterious credit in the ledger.
    """
    return max(0.0, float(position_value) - float(margin_paid))


def days_held(entry: dt.date, exit_: dt.date) -> int:
    """CALENDAR days, inclusive of the entry day.

    Interest does not take the weekend off: a Friday→Monday hold is 3 days of
    funding, not 1. And a same-day open/close is 1 day, not 0 — the position was
    funded for a day, and `exit - entry` would say otherwise.
    """
    if exit_ < entry:
        return 0
    return (exit_ - entry).days + 1


def daily_interest(funded: float, annual_rate: float = DEFAULT_ANNUAL_RATE) -> float:
    """One day's funding cost. Simple, not compounded — brokers bill it daily
    against the funded amount rather than rolling it into the principal."""
    if funded <= 0 or annual_rate <= 0:
        return 0.0
    return funded * float(annual_rate) / DAYS_IN_YEAR


def carry_cost(*, position_value: float, margin_paid: float,
               entry: dt.date, exit_: dt.date,
               annual_rate: float = DEFAULT_ANNUAL_RATE) -> float:
    """Total interest for holding a funded position from `entry` to `exit_`.

    Returned as a POSITIVE number — it is a cost, and the caller subtracts it.
    Returning a negative would invite a sign error in exactly the place a sign
    error is least visible.
    """
    funded = funded_amount(position_value, margin_paid)
    return round(daily_interest(funded, annual_rate) * days_held(entry, exit_), 2)


def accrued_to_date(*, position_value: float, margin_paid: float,
                    entry: dt.date, today: dt.date,
                    annual_rate: float = DEFAULT_ANNUAL_RATE) -> float:
    """Interest owed SO FAR on a still-open position.

    Unrealized P&L on an MTF position must include this, or an open position
    looks better every day it is held — the exact opposite of the truth, and the
    error would compound silently for as long as the position stayed open.
    """
    return carry_cost(position_value=position_value, margin_paid=margin_paid,
                      entry=entry, exit_=today, annual_rate=annual_rate)
