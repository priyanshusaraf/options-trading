"""Qualification — the first, cheapest stage: discover *where* a strategy naturally
works before spending any compute optimizing it. Each instrument is evaluated once
at fixed params; those clearing a hard minimum-evidence bar form the qualifying
universe. Instruments that fail are kept (negative evidence is first-class) with the
reason recorded — that is the raw material for Findings.
"""
from __future__ import annotations

import dataclasses

from research.evaluation import kernels
from research.stats.evidence import bootstrap_mean_lower_bound


@dataclasses.dataclass
class InstrumentEvaluation:
    instrument_key: str
    interval: str
    trades: int
    net_pnls: list
    metrics: object          # BTMetrics
    qualified: bool
    reason: str


@dataclasses.dataclass
class QualificationOutcome:
    evaluations: list        # every InstrumentEvaluation, incl. the rejections
    qualifying_universe: list  # instrument keys that cleared the bar


def qualification_gate(net_pnls, *, min_trades: int, seed: int = 0) -> tuple[bool, str]:
    """Hard gate: enough trades AND a bootstrap lower bound on mean net P&L above
    zero. Returns (passed, reason)."""
    if len(net_pnls) < min_trades:
        return False, f"insufficient trades ({len(net_pnls)}<{min_trades})"
    if bootstrap_mean_lower_bound(net_pnls, seed=seed) <= 0.0:
        return False, "edge not confidently positive (bootstrap LB<=0)"
    return True, "qualified"


def qualify_instrument(candles, inst, interval, strategy, params, *,
                       min_trades: int = 20, seed: int = 0) -> InstrumentEvaluation:
    trades, metrics = kernels.simulate(candles, inst, interval,
                                       strategy=strategy, params=params)
    net = [t.net_pnl for t in trades]
    ok, reason = qualification_gate(net, min_trades=min_trades, seed=seed)
    return InstrumentEvaluation(getattr(inst, "key", ""), interval, len(net),
                                net, metrics, ok, reason)


def qualify(instruments_candles, strategy, params, *, interval: str = "day",
            min_trades: int = 20, seed: int = 0) -> QualificationOutcome:
    """`instruments_candles` is an iterable of (instrument, candles)."""
    evals = [qualify_instrument(candles, inst, interval, strategy, params,
                                min_trades=min_trades, seed=seed)
             for inst, candles in instruments_candles]
    return QualificationOutcome(evals, [e.instrument_key for e in evals if e.qualified])
