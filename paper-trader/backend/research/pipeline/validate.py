"""Validation — the hard gate battery that runs BEFORE ranking. A candidate must
clear every gate to be scored; there is no trading one gate off against another.
Gates: enough out-of-sample trades, temporal stability across walk-forward folds,
a confident (bootstrap) positive edge on pooled OOS trades, and survival under 2x a
per-segment slippage assumption (an edge that dies at plausible slippage is not an
edge). Validation is the OUTER loop; when optimization arrives it runs inside each
fold's in-sample window and is scored on the fold's untouched OOS slice.
"""
from __future__ import annotations

import dataclasses

from research.evaluation.walkforward import walk_forward
from research.stats.evidence import bootstrap_mean_lower_bound


@dataclasses.dataclass
class ValidationOutcome:
    passed: bool
    gates: dict          # name -> {"passed": bool, "value": ...}
    wf: object           # WalkForwardResult


def slippage_stressed_nets(trades, *, slippage_bps: float, mult: float) -> list:
    """Per-trade net P&L after a round-trip slippage charge of `mult * slippage_bps`
    of notional on each side. Duck-typed on the trade (net_pnl, notional/entry_price*qty)."""
    def cost(t):
        notional = getattr(t, "notional", 0.0) or (getattr(t, "entry_price", 0.0) * getattr(t, "qty", 0))
        return 2.0 * (slippage_bps / 10_000.0) * notional * mult
    return [t.net_pnl - cost(t) for t in trades]


def validation_gates(wf, *, min_oos_trades: int = 20, min_positive_fold_frac: float = 0.6,
                     slippage_bps: float = 5.0, slippage_mult: float = 2.0,
                     seed: int = 0) -> dict:
    pooled = [t for f in wf.folds for t in f.trades]
    pooled_net = [t.net_pnl for t in pooled]
    stressed = slippage_stressed_nets(pooled, slippage_bps=slippage_bps, mult=slippage_mult)
    lb = bootstrap_mean_lower_bound(pooled_net, seed=seed) if pooled_net else 0.0
    stressed_mean = (sum(stressed) / len(stressed)) if stressed else 0.0
    return {
        "min_oos_trades": {"passed": wf.total_oos_trades >= min_oos_trades,
                           "value": wf.total_oos_trades},
        "temporal_stability": {"passed": wf.positive_fold_fraction >= min_positive_fold_frac,
                               "value": round(wf.positive_fold_fraction, 3)},
        "confident_edge": {"passed": lb > 0.0, "value": round(lb, 2)},
        "slippage_stress_2x": {"passed": stressed_mean > 0.0, "value": round(stressed_mean, 2)},
    }


def validate(candles, inst, strategy, params, *, n_folds: int = 4,
             capital: float = 50_000.0, **gate_kw) -> ValidationOutcome:
    wf = walk_forward(candles, inst, strategy, params, n_folds=n_folds, capital=capital)
    gates = validation_gates(wf, **gate_kw)
    return ValidationOutcome(all(g["passed"] for g in gates.values()), gates, wf)
