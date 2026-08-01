"""Never hold a futures contract into its delivery window.

Index futures are cash-settled, so for everything E2 trades today this guard is
a no-op. It is built first anyway because the failure it prevents is not a
losing trade: an MCX gold contract held through its compulsory tender period is
an obligation to deliver physical metal, and by the time that is visible it is
a settlement problem rather than a position.

A guard only ever exercised against the always-None calendar is a guard nobody
has tested, so these use a static calendar that actually bites.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.engine.delivery_calendar import (CashSettledCalendar, DeliveryWindow,
                                          StaticDeliveryCalendar,
                                          no_delivery_window)

EXPIRY = dt.date(2026, 8, 27)


def test_cash_settled_index_futures_are_always_safe():
    cal = CashSettledCalendar()
    for day in (dt.date(2026, 8, 1), EXPIRY, EXPIRY - dt.timedelta(days=1)):
        assert no_delivery_window("NIFTY", day, EXPIRY, cal) is True


def test_a_commodity_inside_its_tender_window_is_refused():
    cal = StaticDeliveryCalendar({"GOLDM": 5})
    assert no_delivery_window("GOLDM", EXPIRY - dt.timedelta(days=3), EXPIRY, cal) is False


def test_the_window_is_inclusive_at_both_ends():
    """A contract on the first day of its tender period is exactly as
    undeliverable-from as on the last."""
    cal = StaticDeliveryCalendar({"GOLDM": 5})
    assert no_delivery_window("GOLDM", EXPIRY - dt.timedelta(days=5), EXPIRY, cal) is False
    assert no_delivery_window("GOLDM", EXPIRY, EXPIRY, cal) is False


def test_outside_the_window_is_safe():
    cal = StaticDeliveryCalendar({"GOLDM": 5})
    assert no_delivery_window("GOLDM", EXPIRY - dt.timedelta(days=6), EXPIRY, cal) is True


def test_an_instrument_the_calendar_does_not_know_is_cash_settled():
    """A key with no entry has no delivery risk — that is what the map means."""
    cal = StaticDeliveryCalendar({"GOLDM": 5})
    assert no_delivery_window("NIFTY", EXPIRY, EXPIRY, cal) is True


# ── the adversarial cases the spec asks for ─────────────────────────────────

def test_a_calendar_that_raises_is_treated_as_UNSAFE():
    """Unknown means unsafe. Every other guard here fails closed; this one has
    the most reason to, because the downside of guessing wrong is physical
    settlement rather than a bad fill."""
    class Broken:
        def window_for(self, instrument_key, expiry):
            raise RuntimeError("calendar service down")

    assert no_delivery_window("GOLDM", dt.date(2026, 8, 1), EXPIRY, Broken()) is False


def test_a_calendar_returning_junk_is_treated_as_unsafe():
    class Junk:
        def window_for(self, instrument_key, expiry):
            return "tomorrow-ish"

    assert no_delivery_window("GOLDM", dt.date(2026, 8, 1), EXPIRY, Junk()) is False


def test_true_means_safe_so_a_forgotten_negation_refuses_rather_than_trades():
    """Polarity is load-bearing. TRUE = 'no delivery window in the way', so a
    caller that mixes up the sense gets a refusal, not an unguarded position."""
    cal = StaticDeliveryCalendar({"GOLDM": 5})
    safe = no_delivery_window("GOLDM", dt.date(2026, 1, 1), EXPIRY, cal)
    unsafe = no_delivery_window("GOLDM", EXPIRY, EXPIRY, cal)
    assert safe is True and unsafe is False


def test_the_window_dataclass_is_inclusive():
    w = DeliveryWindow(starts=dt.date(2026, 8, 20), ends=dt.date(2026, 8, 27))
    assert w.contains(dt.date(2026, 8, 20)) is True
    assert w.contains(dt.date(2026, 8, 27)) is True
    assert w.contains(dt.date(2026, 8, 19)) is False
    assert w.contains(dt.date(2026, 8, 28)) is False
