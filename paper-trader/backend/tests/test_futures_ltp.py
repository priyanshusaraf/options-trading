"""Futures must be marked on the FUTURES price, never on spot.

A future trades at a basis to its underlying — carry, dividends, sentiment — and
the gap is not small: an index future can sit tens of points from the cash index
and converges only at expiry. Marking a futures position to spot mis-prices it
on entry, on every risk tick, and at exit, which corrupts unrealized P&L and
every stop distance derived from it. The E2 spec called this out as a real build
item precisely because the seam did not exist.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.providers.base import MarketDataProvider


def _mock():
    """A FRESH MockProvider, never the shared factory singleton.

    `factory.get_provider()` is process-wide, and other tests advance its cursor.
    An earlier cut of this file used it and passed in isolation while failing in
    the full suite: `get_ltp` returned None at whatever position the shared
    provider had been left in, so a test about the BASIS was really asserting
    something about test ordering. A test that depends on shared mutable state
    is not testing what it claims to."""
    from app.providers.mock import MockProvider
    return MockProvider()


def test_the_base_provider_returns_none_rather_than_spot():
    """A provider that cannot fetch a real futures price must SAY SO, so the
    caller refuses the trade. Falling back to spot would be the mis-pricing
    wearing a working provider's clothes — the worst possible failure mode,
    because everything downstream would look healthy."""
    assert MarketDataProvider.get_futures_ltp(
        object(), get_instrument("NIFTY"), dt.date(2026, 8, 27)) is None


def test_the_mock_prices_futures_away_from_spot():
    p = _mock()
    inst = get_instrument("NIFTY")
    spot = p.get_ltp(inst)
    fut = p.get_futures_ltp(inst, p.now().date() + dt.timedelta(days=45))
    assert fut is not None and spot is not None
    assert fut != spot, "a futures price identical to spot models no basis at all"
    assert fut > spot, "positive carry should put the future above spot"


def test_the_basis_converges_at_expiry():
    """The one property of a real future a test must rely on. A flat offset
    would let a bug that ignores expiry pass unnoticed."""
    p = _mock()
    inst = get_instrument("NIFTY")
    today = p.now().date()
    far = p.get_futures_ltp(inst, today + dt.timedelta(days=180))
    near = p.get_futures_ltp(inst, today + dt.timedelta(days=2))
    at_expiry = p.get_futures_ltp(inst, today)
    spot = p.get_ltp(inst)
    assert far > near >= at_expiry
    assert at_expiry == pytest.approx(spot, rel=1e-6)


def test_a_past_expiry_does_not_produce_a_negative_basis():
    """An expired contract must not price BELOW spot through arithmetic — that
    would be an arbitrage the model invented."""
    p = _mock()
    inst = get_instrument("NIFTY")
    stale = p.get_futures_ltp(inst, p.now().date() - dt.timedelta(days=10))
    assert stale >= p.get_ltp(inst)


def test_the_seam_exists_on_the_interface_not_just_the_mock():
    """So a real KiteProvider implementation has somewhere to land, and callers
    can depend on the method existing."""
    assert hasattr(MarketDataProvider, "get_futures_ltp")


def test_the_seam_is_concrete_so_existing_providers_still_construct():
    """Regression for a self-inflicted break.

    The first cut inserted this method between `@abstractmethod` and `get_ltp`,
    which made get_futures_ltp abstract AND silently stripped get_ltp of its
    abstractness. Every provider then failed to instantiate (TypeError) and nine
    tests went red at once. A new optional seam must never make an existing
    provider unconstructable."""
    import inspect
    from app.providers.base import MarketDataProvider
    assert "get_futures_ltp" not in getattr(
        MarketDataProvider, "__abstractmethods__", frozenset())
    assert "get_ltp" in MarketDataProvider.__abstractmethods__, \
        "get_ltp must remain abstract — providers MUST implement it"
    src = inspect.getsource(MarketDataProvider.get_futures_ltp)
    assert "return None" in src
