"""Delivery-window guard for futures — refuse to hold a contract into delivery.

E2 trades INDEX futures, which are cash-settled: there is no physical delivery
and this guard is a documented no-op for every instrument it currently sees. It
exists anyway, and is built first, because the failure it prevents is
unrecoverable and silent until it is not.

MCX commodity futures (gold, silver, crude) enter a compulsory
delivery/tender period BEFORE expiry. A bot holding one through that window is
not carrying a position, it is carrying an obligation to deliver or take
delivery of physical metal — a margin call and a settlement problem, not a
losing trade. The owner's directive is explicit: intraday only, no rollovers,
never hold to delivery.

Two design decisions worth stating, because both invert the usual default:

**Unknown means UNSAFE.** A calendar that raises, or returns something
unparseable, means we do not know whether today is inside a delivery window —
and the safe reading of "I don't know" for an obligation to deliver bullion is
"assume yes". Every other guard in this codebase fails closed; this one has the
most reason to.

**The window is inclusive at both ends.** A contract in its tender period on the
first day is exactly as undeliverable-from as on the last.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Protocol


@dataclasses.dataclass(frozen=True)
class DeliveryWindow:
    starts: dt.date   # first delivery/tender-locked date, inclusive
    ends: dt.date     # expiry / settlement date, inclusive

    def contains(self, day: dt.date) -> bool:
        return self.starts <= day <= self.ends


class DeliveryCalendar(Protocol):
    def window_for(self, instrument_key: str,
                   expiry: dt.date) -> DeliveryWindow | None:
        """None => cash-settled / no delivery risk."""


class CashSettledCalendar:
    """E2's calendar: always None.

    Correct AND permanent for index futures — every NFO/BFO index contract is
    cash-settled — but deliberately inert rather than absent, so the commodity
    extension has a seam to fill instead of a guard to invent under pressure.
    """

    def window_for(self, instrument_key: str,
                   expiry: dt.date) -> DeliveryWindow | None:
        return None


@dataclasses.dataclass(frozen=True)
class StaticDeliveryCalendar:
    """A calendar backed by an explicit {instrument_key: days_before_expiry} map.

    The shape a real MCX staggered-delivery calendar would take. Used in tests
    to prove the guard actually bites, because a guard only ever exercised
    against `CashSettledCalendar` is a guard nobody has tested.
    """
    lead_days: dict

    def window_for(self, instrument_key: str,
                   expiry: dt.date) -> DeliveryWindow | None:
        lead = self.lead_days.get(instrument_key)
        if lead is None:
            return None
        return DeliveryWindow(starts=expiry - dt.timedelta(days=int(lead)),
                              ends=expiry)


def no_delivery_window(instrument_key: str, today: dt.date, expiry: dt.date,
                       calendar: DeliveryCalendar) -> bool:
    """True => safe to hold/open today. False => refuse new entries AND
    force-close any open position immediately, at higher priority than the
    normal end-of-day force-flat.

    Note the return-value polarity: TRUE IS SAFE. It reads as "there is no
    delivery window in the way", so a caller that forgets to negate gets a
    refusal rather than an unguarded trade.
    """
    try:
        window = calendar.window_for(instrument_key, expiry)
    except Exception:
        # Unknown means unsafe. We cannot establish that today is outside a
        # delivery window, and the downside of guessing wrong is physical
        # settlement rather than a bad fill.
        return False
    if window is None:
        return True
    try:
        return not window.contains(today)
    except Exception:
        return False
