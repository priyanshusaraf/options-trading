"""L1 Stage 1 — the numbers Stage 1 is judged on.

The owner's close criteria are quantitative: per-bar agreement ≥ 99.9%, every disagreement
classified, zero unexplained in-hours insufficient-history events, and p95 shadow cost ≤ 20%
of the 2.5 s signal-loop budget. A metric that counts the wrong denominator would make all
four unfalsifiable, so what each one counts is pinned here.
"""
from __future__ import annotations

import datetime as dt

from app.engine import ir_shadow
from app.engine.ir_shadow_metrics import ShadowMetrics

NOW = dt.datetime(2026, 8, 4, 10, 30, 0)


def obs(reason=ir_shadow.AGREEMENT, *, bar=NOW, key="SILVERM", eval_seconds=0.01,
        warmup_state="settled") -> ir_shadow.ShadowObservation:
    flags = dict.fromkeys(("longEntry", "shortEntry", "longExit", "shortExit"), False)
    return ir_shadow.ShadowObservation(
        instrument_key=key, bar_time=bar, observed_at=NOW,
        authoritative_strategy_key="expanding_z_v4",
        shadow_strategy_key="ir.strategy.expanding_z_impulse",
        graph_address="sha256:abc", authoritative=flags, ir=flags,
        warmup_state=warmup_state, declared_warmup=302, frame_bars=400,
        frame_id="sha256:frame", frame_first_ts=NOW, frame_last_ts=bar,
        reason=reason, detail="", eval_seconds=eval_seconds)


# ── agreement is counted per BAR, not per scan ───────────────────────────────────

def test_a_rescanned_bar_is_not_counted_twice():
    """The signal lane re-scans the same completed bar every 2.5 s until the next one
    prints. Counting scans instead of bars would let one agreeing bar, re-read 300 times,
    bury a genuine disagreement under a 99.7% "agreement rate"."""
    metrics = ShadowMetrics()
    for _ in range(50):
        metrics.observe(obs(), market_open=True)
    metrics.observe(obs(bar=NOW + dt.timedelta(minutes=15)), market_open=True)

    snapshot = metrics.snapshot()
    assert snapshot["bars_observed"] == 2
    assert snapshot["agreements"] == 2


def test_bars_on_different_instruments_are_counted_separately():
    metrics = ShadowMetrics()
    metrics.observe(obs(key="SILVERM"), market_open=True)
    metrics.observe(obs(key="GOLDM"), market_open=True)
    assert metrics.snapshot()["bars_observed"] == 2


def test_agreement_rate_is_the_share_of_bars_that_agreed():
    metrics = ShadowMetrics()
    for minute in range(9):
        metrics.observe(obs(bar=NOW + dt.timedelta(minutes=minute)), market_open=True)
    metrics.observe(obs(ir_shadow.FLAG_DIVERGENCE, bar=NOW + dt.timedelta(minutes=99)),
                    market_open=True)

    snapshot = metrics.snapshot()
    assert snapshot["disagreements"] == 1
    assert snapshot["agreement_rate"] == 0.9


def test_agreement_rate_is_none_before_any_bar_rather_than_a_flattering_one():
    """A rate of 1.0 with no data reads as "perfect" on a dashboard. Stage 1 cannot be
    closed on a number that was never measured."""
    assert ShadowMetrics().snapshot()["agreement_rate"] is None


# ── every classification is visible ──────────────────────────────────────────────

def test_every_disagreement_class_is_counted_under_its_own_name():
    metrics = ShadowMetrics()
    for index, reason in enumerate(ir_shadow.DISAGREEMENT_REASONS):
        metrics.observe(obs(reason, bar=NOW + dt.timedelta(minutes=index)),
                        market_open=True)
    by_reason = metrics.snapshot()["by_reason"]
    assert set(by_reason) == set(ir_shadow.DISAGREEMENT_REASONS)
    assert all(count == 1 for count in by_reason.values())


def test_insufficient_history_separates_market_hours_from_outside_them():
    """Criterion 8 is about in-hours refusals: out of hours a short frame means nothing,
    in hours it means the live admission guard and the graph warmup disagree."""
    metrics = ShadowMetrics()
    metrics.observe(obs(ir_shadow.INSUFFICIENT_HISTORY, bar=NOW,
                        warmup_state="insufficient"), market_open=True)
    metrics.observe(obs(ir_shadow.INSUFFICIENT_HISTORY, bar=NOW + dt.timedelta(hours=9),
                        warmup_state="insufficient"), market_open=False)

    snapshot = metrics.snapshot()
    assert snapshot["insufficient_history_in_hours"] == 1
    assert snapshot["insufficient_history_out_of_hours"] == 1


def test_instruments_with_no_mirror_are_counted_not_silently_ignored():
    """Zero shadow coverage and perfect shadow agreement look identical unless the skips
    are counted. Production's default strategy has no mirror, so this is the number that
    says whether any of the others mean anything."""
    metrics = ShadowMetrics()
    metrics.skipped("NIFTY")
    metrics.skipped("BANKNIFTY")
    assert metrics.snapshot()["skipped_no_pairing"] == 2


# ── cost ─────────────────────────────────────────────────────────────────────────

def test_evaluation_cost_reports_p50_p95_and_max():
    metrics = ShadowMetrics()
    for index, seconds in enumerate([0.01] * 90 + [0.2] * 9 + [1.5]):
        metrics.observe(obs(bar=NOW + dt.timedelta(minutes=index),
                            eval_seconds=seconds), market_open=True)

    cost = metrics.snapshot()["eval_seconds"]
    assert cost["count"] == 100
    assert cost["p50"] == 0.01
    assert cost["p95"] == 0.2
    assert cost["max"] == 1.5


def test_cost_is_recorded_even_when_the_evaluation_failed():
    """A refusal that takes a second still costs the loop a second."""
    metrics = ShadowMetrics()
    metrics.observe(obs(ir_shadow.EVALUATION_ERROR, eval_seconds=0.4), market_open=True)
    assert metrics.snapshot()["eval_seconds"]["max"] == 0.4


def test_the_loop_impact_is_measured_against_the_signal_budget():
    metrics = ShadowMetrics()
    metrics.loop(iteration_seconds=1.0, shadow_seconds=0.1, budget_seconds=2.5)
    metrics.loop(iteration_seconds=3.0, shadow_seconds=0.2, budget_seconds=2.5)

    loop = metrics.snapshot()["loop"]
    assert loop["iterations"] == 2
    assert loop["budget_seconds"] == 2.5
    assert loop["overruns"] == 1                    # one iteration outran the 2.5 s tick
    assert loop["max_iteration_seconds"] == 3.0
    assert loop["shadow_seconds"]["max"] == 0.2
    # The criterion is p95 shadow cost ≤ 20% of the budget, so the share must be reported
    # as a share and not left to be recomputed by whoever reads it.
    assert loop["shadow_share_p95"] == 0.2 / 2.5


def test_memory_stays_bounded_over_a_long_session():
    """The box is 1 GB and has OOM'd twice. A metric that keeps every sample is a leak."""
    metrics = ShadowMetrics(sample_limit=100)
    for index in range(5000):
        metrics.observe(obs(bar=NOW + dt.timedelta(minutes=index)), market_open=True)
    assert len(metrics._eval_samples) == 100
    assert metrics.snapshot()["bars_observed"] == 5000


def test_metrics_never_raise_on_a_malformed_observation():
    """This runs inside the signal lane. A metric that throws is a metric that stops the
    engine, which is exactly what the shadow lane is not allowed to do."""
    metrics = ShadowMetrics()
    metrics.observe(None, market_open=True)
    metrics.observe(obs(bar=None, eval_seconds=0.3), market_open=True)

    snapshot = metrics.snapshot()
    # An observation with no bar timestamp is not a bar and must not enter the agreement
    # denominator — but it still cost the loop, so its time is counted.
    assert snapshot["bars_observed"] == 0
    assert snapshot["eval_seconds"]["max"] == 0.3
