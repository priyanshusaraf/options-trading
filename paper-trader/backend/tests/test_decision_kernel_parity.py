"""Phase G — one decision kernel for live, replay and backtest.

Two claims are under test, and the second is the one that has value:

  1. The kernel reproduces the two live exit functions EXACTLY. They were extracted,
     not redesigned, so any difference is a regression in real-money exit logic.
     Asserted by driving both the wrapper and the kernel over a grid of cases and
     demanding identical answers.

  2. Where the backtester still differs from live, the difference is DECLARED.
     `backtest/engine.py` used to note in prose that the live premium stop/target
     "is not modelled here" — true, invisible in the output, and attached to the
     numbers only by whoever remembered to read the docstring. Now the absence is a
     policy object that reports itself, and a test fails if someone removes the
     explanation.
"""
from __future__ import annotations

import itertools

import pytest

from app.engine import decision_kernel as dk
from app.engine.equity_entry import equity_exit
from app.engine.exit_monitor import evaluate_exit

# A grid that covers each branch and, importantly, the BOUNDARIES — `price == stop`
# and `price == target` are where a `<` vs `<=` slip hides, and both live functions
# use inclusive comparisons.
PRICES = (-1.0, 0.0, 0.5, 80.0, 99.999, 100.0, 100.001, 120.0, 150.0)
FLAGS = (False, True)


@pytest.mark.parametrize("price,long_exit,short_exit,target_disabled,ratchet",
                         list(itertools.product(PRICES, FLAGS, FLAGS, FLAGS, FLAGS)))
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_options_wrapper_matches_the_kernel(direction, price, long_exit,
                                            short_exit, target_disabled, ratchet):
    stop, target = 100.0, 150.0
    via_wrapper = evaluate_exit(direction, stop, target, price,
                                long_exit, short_exit,
                                target_disabled=target_disabled,
                                ratchet_exit=ratchet)
    via_kernel = dk.decide_exit(
        direction=direction, price=price, stop=stop, target=target,
        long_exit=long_exit, short_exit=short_exit, ratchet_exit=ratchet,
        policy=dk.ExitPolicy.live_options(target_enabled=not target_disabled),
    ).as_tuple()
    assert via_wrapper == via_kernel


@pytest.mark.parametrize("price,long_exit,short_exit,target_disabled",
                         list(itertools.product(PRICES, FLAGS, FLAGS, FLAGS)))
@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_equity_wrapper_matches_the_kernel(direction, price, long_exit,
                                           short_exit, target_disabled):
    # A SHORT's band is inverted: stop above, target below.
    stop, target = (100.0, 150.0) if direction == "LONG" else (150.0, 100.0)
    should, reason = equity_exit(direction, price, stop, target,
                                 long_exit, short_exit,
                                 target_disabled=target_disabled)
    kernel = dk.decide_exit(
        direction=direction, price=price, stop=stop, target=target,
        long_exit=long_exit, short_exit=short_exit,
        policy=dk.ExitPolicy.live_directional(target_enabled=not target_disabled))
    assert (should, reason) == (kernel.should_exit, kernel.reason or "")


# ── the specific behaviours that must not be lost in the extraction ───────────

def test_a_non_positive_premium_never_fires_a_stop():
    """L13. An option cannot trade at <= 0, so a zero/negative mark is a bad tick,
    not a floor. Firing a real market STOP on a feed gap is the failure this guard
    exists to prevent — and the kernel is now the only place it lives."""
    for bad in (0.0, -1.0, -99.0):
        should, reason = evaluate_exit("LONG", 100.0, 150.0, bad, False, False)
        assert (should, reason) != (True, dk.STOP_LOSS), \
            f"premium {bad} must not trip the stop"


def test_stop_wins_over_target_and_flags():
    """Precedence is policy: the stop bounds loss, so it takes any tie."""
    d = dk.decide_exit(direction="LONG", price=1.0, stop=100.0, target=150.0,
                       long_exit=True, ratchet_exit=True,
                       policy=dk.ExitPolicy.live_options())
    assert d.reason == dk.STOP_LOSS


def test_ratchet_is_evaluated_before_the_strategy_flag():
    """Matches the backtest's own ordering — the two already agreed here and the
    extraction preserves it rather than re-deciding it."""
    d = dk.decide_exit(direction="LONG", price=120.0, stop=100.0, target=150.0,
                       long_exit=True, ratchet_exit=True,
                       policy=dk.ExitPolicy.live_options())
    assert d.reason == dk.RATCHET_STOP


def test_a_shorts_stop_is_above_entry_on_the_directional_band():
    should, reason = equity_exit("SHORT", 151.0, 150.0, 100.0, False, False)
    assert (should, reason) == (True, dk.STOP_LOSS)


# ── declared divergence ──────────────────────────────────────────────────────

def test_backtest_policy_declares_its_divergence():
    from app.backtest.engine import BACKTEST_EXIT_POLICY
    divergences = BACKTEST_EXIT_POLICY.divergences()
    assert divergences, \
        "the backtest policy must REPORT that it does not model the protective band"
    assert any("stop/target" in d for d in divergences)
    assert any("premium" in d for d in divergences), \
        "the divergence must explain WHY, not merely that it exists"


def test_an_undocumented_divergence_cannot_be_declared():
    """The note is mandatory. Without this, `no_protective_band()` becomes an easy
    way to silence the very thing the policy exists to surface."""
    with pytest.raises(ValueError, match="requires a note"):
        dk.ExitPolicy.no_protective_band("")


def test_full_live_policy_reports_no_divergence():
    assert dk.ExitPolicy.live_options().divergences() == []
    assert dk.ExitPolicy.live_directional().divergences() == []


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
@pytest.mark.parametrize("price", [-1e9, 0.0, 1e9])
def test_an_unset_level_never_fires(direction, price):
    """`None` means "not set" and must be inert in BOTH directions.

    This test caught a real bug in the first version of this kernel: it used
    `NO_STOP = -inf`, which on the directional SHORT path (`price >= stop`) means
    "stopped at any price" — every short would have exited instantly with reason
    STOP_LOSS. A sentinel whose meaning flips with direction is not a sentinel."""
    d = dk.decide_exit(direction=direction, price=price, stop=None, target=None,
                       long_exit=False, short_exit=False,
                       policy=dk.ExitPolicy(protective_band=True))
    assert d.should_exit is False
