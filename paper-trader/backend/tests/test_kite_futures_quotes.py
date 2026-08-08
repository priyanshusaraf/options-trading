"""Kite must price the futures contract a position is actually IN.

`get_futures_ltp` was the base class no-op returning `None` until 2026-08-09, while `runner.py`
called it at three sites to mark futures positions, judge staleness, and price the
delivery-window force close. A position would never have marked on a real price and would have
been force-closed at its **entry** price. The `FUTURES_QUOTES` capability guard is what made
leaving that unimplemented safe; this is the implementation that lets the guard open.

The load-bearing behaviour is **exact expiry matching**. `_near_future` returns the front month
by design, and a held position is in the series it was opened in — marking it against the front
month after a rollover prices a different contract at a different basis. That failure is silent
and profitable-looking, which is the worst kind.

These tests stub the instruments dump and the quote call, so they prove the *mapping and
refusal* logic. They do not and cannot prove the live Kite feed works; that needs a real session
and is production verification, not a unit test.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.providers import capabilities as caps
from app.providers.kite import KiteProvider

AUG = dt.date(2026, 8, 27)
SEP = dt.date(2026, 9, 24)

DUMP = [
    {"name": "GOLDM", "instrument_type": "FUT", "expiry": "2026-08-27",
     "tradingsymbol": "GOLDM26AUGFUT", "instrument_token": 111},
    {"name": "GOLDM", "instrument_type": "FUT", "expiry": "2026-09-24",
     "tradingsymbol": "GOLDM26SEPFUT", "instrument_token": 222},
    {"name": "GOLDM", "instrument_type": "CE", "expiry": "2026-08-27",
     "tradingsymbol": "GOLDM26AUG72000CE", "instrument_token": 333},
]


@pytest.fixture
def provider(monkeypatch):
    p = KiteProvider.__new__(KiteProvider)
    monkeypatch.setattr(KiteProvider, "_instruments", lambda self, exch: DUMP)
    monkeypatch.setattr(KiteProvider, "_name_candidates", lambda self, inst: ["GOLDM"])
    return p


@pytest.fixture
def goldm():
    return get_instrument("GOLDM")


def _quotes(monkeypatch, mapping):
    monkeypatch.setattr(KiteProvider, "_ltp", lambda self, keys: mapping)


def test_kite_now_declares_it_can_price_futures():
    assert caps.FUTURES_QUOTES in KiteProvider.CAPABILITIES


def test_it_prices_the_exact_expiry_requested(provider, goldm, monkeypatch):
    _quotes(monkeypatch, {"MCX:GOLDM26SEPFUT": {"last_price": 74_500.0}})
    assert provider.get_futures_ltp(goldm, SEP) == 74_500.0


def test_it_does_not_mark_a_september_position_against_the_august_front_month(
        provider, goldm, monkeypatch):
    """The defect this exists to prevent. `_near_future` returns August; a September position
    marked against it prices a different contract at a different basis, silently."""
    _quotes(monkeypatch, {"MCX:GOLDM26AUGFUT": {"last_price": 72_000.0},
                          "MCX:GOLDM26SEPFUT": {"last_price": 74_500.0}})
    assert provider.get_futures_ltp(goldm, SEP) == 74_500.0, "marked the wrong series"
    assert provider.get_futures_ltp(goldm, AUG) == 72_000.0


def test_an_expiry_with_no_contract_refuses_rather_than_guessing(provider, goldm, monkeypatch):
    """`None` means "I cannot price this". Falling back to the nearest contract, or to spot,
    prices a different economic instrument."""
    _quotes(monkeypatch, {"MCX:GOLDM26AUGFUT": {"last_price": 72_000.0}})
    assert provider.get_futures_ltp(goldm, dt.date(2027, 1, 28)) is None


def test_an_unparseable_expiry_refuses(provider, goldm, monkeypatch):
    _quotes(monkeypatch, {})
    assert provider.get_futures_ltp(goldm, None) is None
    assert provider.get_futures_ltp(goldm, "not-a-date") is None


def test_it_never_resolves_an_option_row_as_a_future(provider, goldm, monkeypatch):
    """The dump holds a CE at the same name and expiry. Matching on expiry alone would price an
    option premium as a futures price — off by orders of magnitude and entirely plausible."""
    _quotes(monkeypatch, {"MCX:GOLDM26AUGFUT": {"last_price": 72_000.0},
                          "MCX:GOLDM26AUG72000CE": {"last_price": 850.0}})
    assert provider.get_futures_ltp(goldm, AUG) == 72_000.0


def test_a_quote_failure_refuses_rather_than_raising(provider, goldm, monkeypatch):
    """A broker error must not propagate into the risk loop — nothing may block an exit."""
    def _boom(self, keys):
        raise RuntimeError("kite is down")
    monkeypatch.setattr(KiteProvider, "_ltp", _boom)
    assert provider.get_futures_ltp(goldm, AUG) is None


def test_a_missing_last_price_refuses(provider, goldm, monkeypatch):
    """A quote that comes back without a price is not a price."""
    _quotes(monkeypatch, {"MCX:GOLDM26AUGFUT": {}})
    assert provider.get_futures_ltp(goldm, AUG) is None
