"""Sizing an index-futures position — in LOTS, against REAL margin.

SPAN is portfolio-scanned and instrument-specific: it is not price times a
leverage constant. So in live mode the broker is the only source of truth, and
when it cannot answer the correct behaviour is to refuse rather than to
estimate. `open_futures_position` already rejects a missing margin, so this
sizer returning None is what keeps a fabricated SPAN figure out of the ledger.

Paper mode uses a flagged percentage-of-notional approximation so backtests can
size something plausible — clearly labelled, and never what a live position is
booked against.
"""
from __future__ import annotations

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.providers.kite import KiteProvider as _KiteForCaps


@pytest.fixture
def runner():
    init_db(reset=True)
    r = EngineRunner()
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


NIFTY = None


def _inst():
    return get_instrument("NIFTY")


def test_paper_mode_sizes_from_the_flagged_percentage(runner):
    sizer = runner._futures_margin_sizer()
    out = sizer(_inst(), "LONG", 24_000.0, 50, 200_000.0)
    assert out is not None
    qty, margin = out
    assert qty % 50 == 0, "quantity must be whole lots"
    assert margin <= 200_000.0


def test_it_returns_whole_lots_only(runner):
    """A futures position that is not a multiple of the lot size is not a
    position the exchange will accept. Rounding at order time would mean the
    sizing that was risk-checked is not the sizing that gets sent."""
    sizer = runner._futures_margin_sizer()
    for target in (150_000.0, 220_000.0, 999_999.0):
        qty, _ = sizer(_inst(), "LONG", 24_000.0, 50, target)
        assert qty % 50 == 0


def test_a_budget_too_small_for_one_lot_is_no_trade(runner):
    """Not a fractional lot, and not a lot bought on more margin than allowed."""
    sizer = runner._futures_margin_sizer()
    assert sizer(_inst(), "LONG", 24_000.0, 50, 100.0) is None


def test_degenerate_inputs_return_none(runner):
    sizer = runner._futures_margin_sizer()
    assert sizer(_inst(), "LONG", 0.0, 50, 200_000.0) is None
    assert sizer(_inst(), "LONG", 24_000.0, 50, 0.0) is None


def test_more_margin_buys_more_lots(runner):
    sizer = runner._futures_margin_sizer()
    small, _ = sizer(_inst(), "LONG", 24_000.0, 50, 200_000.0)
    large, _ = sizer(_inst(), "LONG", 24_000.0, 50, 800_000.0)
    assert large > small


def test_live_mode_refuses_when_the_broker_cannot_quote(runner, monkeypatch):
    """The one that matters. Unlike equity — which may fall back to a leverage
    model — there is NO fallback here: guessing SPAN would put a fabricated
    number straight into the ledger."""
    monkeypatch.setattr(runner.provider, "name", "kite", raising=False)
    monkeypatch.setattr(runner.provider, "CAPABILITIES",
                        _KiteForCaps.CAPABILITIES, raising=False)
    monkeypatch.setattr(runner.provider, "is_authenticated", lambda: True, raising=False)
    monkeypatch.setattr(runner.provider, "order_margin", lambda orders: 0.0,
                        raising=False)
    sizer = runner._futures_margin_sizer()
    assert sizer(_inst(), "LONG", 24_000.0, 50, 500_000.0) is None


def test_live_mode_sizes_from_the_real_quote(runner, monkeypatch):
    monkeypatch.setattr(runner.provider, "name", "kite", raising=False)
    monkeypatch.setattr(runner.provider, "CAPABILITIES",
                        _KiteForCaps.CAPABILITIES, raising=False)
    monkeypatch.setattr(runner.provider, "is_authenticated", lambda: True, raising=False)
    monkeypatch.setattr(runner.provider, "order_margin", lambda orders: 120_000.0,
                        raising=False)
    sizer = runner._futures_margin_sizer()
    qty, margin = sizer(_inst(), "LONG", 24_000.0, 50, 260_000.0)
    assert qty == 100          # two lots at ₹120k each fits ₹260k
    assert margin == pytest.approx(240_000.0)


def test_the_live_quote_is_cached_per_symbol_and_side(runner, monkeypatch):
    """order_margins is rate-limited; a full entry cycle must make at most one
    quote per (symbol, side)."""
    calls = []
    monkeypatch.setattr(runner.provider, "name", "kite", raising=False)
    monkeypatch.setattr(runner.provider, "CAPABILITIES",
                        _KiteForCaps.CAPABILITIES, raising=False)
    monkeypatch.setattr(runner.provider, "is_authenticated", lambda: True, raising=False)
    monkeypatch.setattr(runner.provider, "order_margin",
                        lambda orders: (calls.append(1), 120_000.0)[1], raising=False)
    sizer = runner._futures_margin_sizer()
    for _ in range(4):
        sizer(_inst(), "LONG", 24_000.0, 50, 500_000.0)
    assert len(calls) == 1


def test_a_sized_position_can_actually_be_opened(runner):
    """End to end: whatever the sizer returns must satisfy the broker's
    non-negotiable margin requirement."""
    import datetime as dt
    sizer = runner._futures_margin_sizer()
    qty, margin = sizer(_inst(), "LONG", 24_000.0, 50, 200_000.0)
    pos = runner.broker.open_futures_position(
        _inst(), "LONG", 24_000.0, qty, "NFO_FUT", "TEST",
        dt.datetime(2026, 8, 3, 10, 0), dt.date(2026, 8, 27), margin=margin)
    assert pos.qty == qty
