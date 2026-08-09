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


def test_a_past_expiry_is_refused_rather_than_clamped_to_spot():
    """An expired contract has no price at all, and that supersedes the older contract here.

    This test previously required only that a past expiry not price BELOW spot — an arbitrage
    the model would have invented — which the `max(0, days)` clamp satisfied by returning
    exactly spot. Returning spot for a settled contract is the same substitution
    `get_futures_ltp` exists to prevent, wearing a different disguise: the caller cannot tell a
    converged future from a contract that no longer exists.

    Refusing is also the only refusal a synthetic market can genuinely make — every FUTURE
    expiry exists in the mock — so it is what makes the conformance obligation "price it or
    refuse, never substitute the underlying" testable against the mock rather than vacuous.
    """
    p = _mock()
    inst = get_instrument("NIFTY")
    spot = p.get_ltp(inst)
    stale = p.get_futures_ltp(inst, p.now().date() - dt.timedelta(days=10))
    assert stale is None, "a settled contract cannot be marked"
    assert stale != spot, "and in particular it must not come back as the underlying"
    assert p.get_futures_ltp(inst, p.now().date()) == pytest.approx(spot, rel=1e-6), (
        "settlement day itself still prices, at convergence — the refusal starts after it")


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
