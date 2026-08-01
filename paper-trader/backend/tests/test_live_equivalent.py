"""Backtest edge -> live rupees, without inventing the missing number.

The backtester audit called backtest-vs-live sizing the biggest interpretive
trap here: the backtest holds one unleveraged position on full capital, while
production sizes against real MIS margin across up to four concurrent slots. A
backtest `net_pnl` is therefore not a prediction of live rupees, and reading it
as one is the single easiest mistake to make with these numbers.

The conversion needs one input nobody has offline: per-share MIS margin. These
tests pin that the module REFUSES rather than guesses — a projection with a
fabricated leverage buried in it would be worse than no projection, because it
would look authoritative.
"""
from __future__ import annotations

import pytest

from app.backtest.live_equivalent import project


BASE = dict(backtest_net_pnl=1000.0, backtest_qty=100, entry_price=500.0,
            target_margin=10_000.0)


def test_it_refuses_without_a_real_margin_quote():
    """The honest answer to 'what would this have made live?' when the margin is
    unknown is NO NUMBER — not a number with a guessed leverage inside it."""
    assert project(**BASE, per_share_margin=None) is None
    assert project(**BASE, per_share_margin=0.0) is None


def test_it_scales_the_per_share_edge():
    r = project(**BASE, per_share_margin=100.0)
    assert r.per_share_pnl == pytest.approx(10.0)     # 1000 / 100 shares
    assert r.live_qty == 100                          # 10,000 margin / 100 per share
    assert r.projected_pnl == pytest.approx(1000.0)


def test_leverage_shows_up_as_a_bigger_position():
    """Lower per-share margin = more shares for the same rupees of margin. This
    is the whole reason live and backtest quantities diverge."""
    tight = project(**BASE, per_share_margin=500.0)   # no leverage: margin == price
    levered = project(**BASE, per_share_margin=100.0)  # 5x
    assert levered.live_qty == 5 * tight.live_qty
    assert levered.projected_pnl > tight.projected_pnl


def test_concurrency_multiplies_the_book_not_the_position():
    r = project(**BASE, per_share_margin=100.0, concurrency=4)
    assert r.projected_pnl_all_slots == pytest.approx(r.projected_pnl * 4)
    assert r.concurrency == 4


def test_the_scale_factor_states_how_different_the_two_models_are():
    r = project(**BASE, per_share_margin=100.0)
    assert r.scale_vs_backtest == pytest.approx(1.0)
    r2 = project(**BASE, per_share_margin=50.0)
    assert r2.scale_vs_backtest == pytest.approx(2.0)


def test_the_assumption_travels_with_the_number():
    """A projection separated from its assumptions becomes a fact. The caveat is
    a FIELD, not a docstring, so it cannot be dropped on the way to a report."""
    r = project(**BASE, per_share_margin=100.0)
    assert "market impact" in r.assumption
    assert "same price" in r.assumption


def test_a_position_too_small_to_open_is_not_a_projection():
    """Margin per share above the whole target buys zero shares."""
    assert project(**BASE, per_share_margin=50_000.0) is None


def test_degenerate_backtests_return_nothing():
    assert project(backtest_net_pnl=0.0, backtest_qty=0, entry_price=100.0,
                   per_share_margin=10.0, target_margin=1000.0) is None
    assert project(backtest_net_pnl=10.0, backtest_qty=5, entry_price=0.0,
                   per_share_margin=10.0, target_margin=1000.0) is None


def test_a_losing_edge_projects_a_larger_loss_when_levered():
    """Leverage is symmetric, and a projection that only scaled winners would be
    a marketing tool rather than a model."""
    r = project(backtest_net_pnl=-1000.0, backtest_qty=100, entry_price=500.0,
                per_share_margin=100.0, target_margin=50_000.0)
    assert r.projected_pnl < -1000.0
