"""L1 Stage 1 — a graph may not be shadowed unless its warmup can actually be satisfied.

The Stage 1 measurement surfaced ADR 0011 conflict #2 as a live fact: the graph's resolved
warmup is 302 bars, and whether the configured history and timeframe can ever produce 303
depends entirely on the instrument's session length and live interval. An NSE name on 30m
yields ~273 bars in 30 calendar days and **can never settle** — so without this validator the
lane would refuse that instrument on every scan, all session, forever.

The rule this file pins: decide *before* evaluating, decide from configuration rather than
from a failure, and make a rejection **visible and terminal** rather than a refusal repeated
every 2.5 seconds.
"""
from __future__ import annotations

import pytest

from app.engine import ir_shadow

WARMUP = 302


def admit(segment="NSE", interval="15minute", history_days=30, warmup=WARMUP,
          instrument_key="NIFTY"):
    return ir_shadow.admit(instrument_key=instrument_key, segment=segment,
                           interval=interval, history_days=history_days, warmup=warmup)


# ── the arithmetic, stated so it can be checked ──────────────────────────────────

@pytest.mark.parametrize("segment,interval,expected", [
    ("NSE", "5minute", 75),      # 09:15–15:30 = 375 minutes
    ("NSE", "15minute", 25),
    ("NSE", "30minute", 13),     # 12.5 rounds UP: the stub bar at the close is a bar
    ("NSE", "60minute", 7),
    ("MCX", "15minute", 58),     # 09:00–23:30 = 870 minutes
    ("MCX", "60minute", 15),
])
def test_bars_per_session_follows_the_segment_session_and_the_interval(
        segment, interval, expected):
    assert ir_shadow.bars_per_session(segment, interval) == expected


def test_trading_sessions_are_counted_conservatively_from_calendar_days():
    """`history_days` is calendar days. Five sessions a week, floored — an optimistic count
    would admit a graph that then refuses in the middle of a session, which is the failure
    this validator exists to prevent."""
    assert ir_shadow.trading_sessions(30) == 21
    assert ir_shadow.trading_sessions(7) == 5
    assert ir_shadow.trading_sessions(0) == 0


# ── the verdict ──────────────────────────────────────────────────────────────────

def test_a_configuration_that_can_settle_the_warmup_is_admitted():
    verdict = admit(segment="NSE", interval="15minute")
    assert verdict.ok is True
    assert verdict.expected_bars == 21 * 25 == 525
    assert verdict.warmup == WARMUP


def test_the_thirty_minute_configuration_that_can_never_settle_is_refused():
    """The finding from the Stage 1 measurement, as a guard."""
    verdict = admit(segment="NSE", interval="30minute")
    assert verdict.ok is False
    assert verdict.expected_bars == 273
    assert "273" in verdict.reason and "302" in verdict.reason


def test_the_sixty_minute_configuration_is_refused_too():
    assert admit(segment="NSE", interval="60minute").ok is False


def test_a_commodity_session_is_long_enough_to_admit_the_same_graph():
    """MCX runs 09:00–23:30, so the same graph and the same `history_days` clear the warmup
    where an NSE name does not. The rejection is about configuration, not about the graph."""
    assert admit(segment="MCX", interval="60minute").ok is True


def test_exactly_warmup_bars_is_not_enough():
    """A settled bar is one *after* the warmup. Admitting on equality would admit a
    configuration whose only possible output is the warmup mask."""
    interval, segment = "15minute", "NSE"
    per_session = ir_shadow.bars_per_session(segment, interval)
    verdict = admit(segment=segment, interval=interval,
                    warmup=ir_shadow.trading_sessions(30) * per_session)
    assert verdict.ok is False


def test_an_unknown_segment_falls_back_to_the_shortest_session_not_the_longest():
    """Fail closed: guessing the MCX session for an unknown segment would admit a
    configuration that cannot settle."""
    assert ir_shadow.bars_per_session("NO_SUCH_SEGMENT", "15minute") == \
        ir_shadow.bars_per_session("NSE", "15minute")


def test_an_unknown_interval_is_refused_rather_than_guessed():
    verdict = admit(interval="7minute")
    assert verdict.ok is False
    assert "7minute" in verdict.reason


# ── the runner: a rejection is visible, and it happens once ──────────────────────

def _runner(monkeypatch, interval="15minute"):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    runner = EngineRunner()
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
        runner.intervals[key] = interval
    return runner


def _short_feed(runner, monkeypatch, bars: int = 161):
    """Force the provider to hand back a frame too short to settle the graph.

    Made explicit rather than relied upon. The mock provider is a process-wide singleton
    whose cursor advances as other tests run, so a test that merely *assumed* a short frame
    passed alone and failed in the full suite once something else had advanced it past the
    warmup. The condition under test — the feed contradicting the admission arithmetic — is
    now stated in the test instead of inherited from suite order.
    """
    original = runner.provider.get_candles
    monkeypatch.setattr(runner.provider, "get_candles",
                        lambda *args, **kwargs: original(*args, **kwargs)[-bars:])
    return bars


def _split_by_admissibility(runner, interval: str, warmup: int = WARMUP):
    """Which of the enabled instruments this interval can and cannot settle.

    Computed rather than hard-coded, because the answer is **segment-dependent**: MCX runs
    09:00–23:30 and clears a 302-bar warmup at 30 minutes where an NSE name cannot. A test
    that assumed "30 minutes rejects everything" would have been asserting a bug.
    """
    from app.core.instruments import get_instrument

    rejected, admitted = set(), set()
    for key in runner.enabled:
        verdict = ir_shadow.admit(
            instrument_key=key, segment=get_instrument(key).segment, interval=interval,
            history_days=int(runner.settings.history_days), warmup=warmup)
        (admitted if verdict.ok else rejected).add(key)
    return admitted, rejected


def test_an_inadmissible_pairing_is_never_evaluated(monkeypatch):
    """Not "evaluated and refused" — not evaluated. A refusal repeated every 2.5 s for a
    whole session is the noise this validator removes, and it costs the loop real time."""
    runner = _runner(monkeypatch, interval="30minute")
    admitted, rejected = _split_by_admissibility(runner, "30minute")
    assert rejected, "fixture must contain at least one inadmissible instrument"
    calls = []
    monkeypatch.setattr(ir_shadow, "observe",
                        lambda **kwargs: calls.append(kwargs["instrument_key"]) or None)

    runner.scan_signals()

    assert set(calls) == admitted        # the rejected ones were never evaluated at all
    assert runner.shadow_metrics.snapshot()["rejected_pairings"] == len(rejected)


def test_a_rejection_names_the_instrument_and_the_reason(monkeypatch):
    runner = _runner(monkeypatch, interval="30minute")
    _, rejected = _split_by_admissibility(runner, "30minute")

    runner.scan_signals()

    rejections = runner.shadow_metrics.snapshot()["rejections"]
    assert set(rejections) == rejected
    for key, reason in rejections.items():
        assert key in reason and "302" in reason and "30minute" in reason


def test_the_rejection_is_logged_once_not_once_a_scan(monkeypatch):
    """Visible, then quiet. The 2026-07 log-flood incident is the precedent."""
    runner = _runner(monkeypatch, interval="30minute")
    _, rejected = _split_by_admissibility(runner, "30minute")
    logged = []
    from app.core import logging as log_module
    monkeypatch.setattr(log_module.log, "warn",
                        lambda message, **kwargs: logged.append(message))

    for _ in range(5):
        runner.scan_signals()

    admission_logs = [line for line in logged if "REJECTED at admission" in line]
    assert len(admission_logs) == len(rejected)


def test_changing_the_interval_re_decides_admission(monkeypatch):
    """The verdict is a function of (instrument, interval), so a live interval change must
    not leave a stale rejection in place — or fixing the configuration would need a
    restart, which Stage 1 criterion 5 forbids."""
    runner = _runner(monkeypatch, interval="30minute")
    runner.scan_signals()
    assert runner.shadow_metrics.snapshot()["rejected_pairings"] > 0
    assert runner.shadow_metrics.snapshot()["bars_observed"] < len(runner.enabled)

    for key in list(runner.enabled):
        runner.intervals[key] = "15minute"
    runner.scan_signals()

    assert runner.shadow_metrics.snapshot()["bars_observed"] == len(runner.enabled)


def test_an_admitted_pairing_that_still_refuses_is_counted_separately(monkeypatch):
    """Criterion 9 says zero unexplained insufficient-history events **after admission**.
    An admitted pairing that refuses anyway is a defect in the validator, so it must be
    distinguishable from the ordinary pre-admission case rather than blending into it."""
    runner = _runner(monkeypatch, interval="15minute")
    _short_feed(runner, monkeypatch)

    runner.scan_signals()

    snapshot = runner.shadow_metrics.snapshot()
    # Admission reasons from configuration and says yes; the frame says no. That is exactly
    # the anomaly this counter exists to make loud.
    assert snapshot["insufficient_history_after_admission"] == len(runner.enabled)


# ── when the feed disagrees with the admission arithmetic ────────────────────────

def test_an_admitted_pairing_that_keeps_refusing_is_demoted_rather_than_left_to_repeat(
        monkeypatch):
    """Admission reasons from configuration; the feed can still disagree with it.

    The mock provider is the standing example — it hands back 161 bars whatever interval or
    `history_days` it is asked for, so admission says 525 and the frame says 161. Predicting
    correctly is not enough: the contract is that a pairing **cannot** produce repeated
    in-hours `INSUFFICIENT_HISTORY`, so an admitted pairing that keeps refusing is demoted
    to rejected, with a reason naming both numbers.
    """
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    runner = EngineRunner()
    runner.params["ir_shadow_enabled"] = True
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
        runner.intervals[key] = "15minute"
    bars = _short_feed(runner, monkeypatch)

    for _ in range(ir_shadow.REFUSALS_BEFORE_DEMOTION + 3):
        runner.scan_signals()

    snapshot = runner.shadow_metrics.snapshot()
    assert snapshot["rejected_pairings"] == len(runner.enabled)
    # One per instrument, not one per scan: the metric counts BARS, and the mock's newest
    # bar does not change between scans. The refusal streak that drives the demotion counts
    # scans, which is why the two numbers differ and why both are needed — a bar-deduped
    # counter alone could never see a refusal repeating.
    assert (snapshot["insufficient_history_after_admission"] == len(runner.enabled))
    for reason in snapshot["rejections"].values():
        assert str(bars) in reason and "demoted" in reason.lower()


def test_a_demotion_is_cleared_by_an_interval_change_like_any_other_rejection(monkeypatch):
    """A demotion is a verdict about a configuration, not a permanent mark on the
    instrument — otherwise fixing the feed would need a restart."""
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    runner = EngineRunner()
    runner.params["ir_shadow_enabled"] = True
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
        runner.intervals[key] = "15minute"
    _short_feed(runner, monkeypatch)
    for _ in range(ir_shadow.REFUSALS_BEFORE_DEMOTION + 1):
        runner.scan_signals()
    assert runner.shadow_metrics.snapshot()["rejected_pairings"] > 0

    for key in list(runner.enabled):
        runner.intervals[key] = "5minute"
    runner.scan_signals()

    assert runner.shadow_metrics.snapshot()["rejections"] == {}
