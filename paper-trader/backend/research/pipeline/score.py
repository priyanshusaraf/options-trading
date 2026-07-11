"""Scoring — ranks ONLY validated candidates. Deliberately not a single gameable
weighted composite: the primary key is the Deflated Sharpe Ratio (hardest to game),
and `pareto_front` exposes the non-dominated set across chosen dimensions so the
human sees the trade-offs rather than trusting invented weights. Every component is
logged on the scorecard for auditability.
"""
from __future__ import annotations

import dataclasses

from research.stats.dsr import deflated_sharpe


@dataclasses.dataclass
class Scorecard:
    key: str
    dsr: float
    components: dict


def build_scorecard(key: str, metrics, *, n_trials: int = 1, var_sr: float = 0.0,
                    skew: float = 0.0, kurt: float = 3.0) -> Scorecard:
    """DSR from the per-trade Sharpe (`metrics.consistency`) and trade count, deflated
    by the number of trials that produced it. Fewer than 2 trades -> DSR 0."""
    sr = metrics.consistency or 0.0
    dsr = (deflated_sharpe(sr, metrics.trades, skew=skew, kurt=kurt,
                           n_trials=n_trials, var_sr=var_sr)
           if metrics.trades >= 2 else 0.0)
    components = {
        "dsr": round(dsr, 4),
        "per_trade_sharpe": round(sr, 4),
        "sharpe": metrics.sharpe,
        "calmar": metrics.calmar,
        "profit_factor": metrics.profit_factor,
        "return_pct": round(metrics.return_pct, 2),
        "max_drawdown_pct": round(metrics.max_drawdown_pct, 2),
        "worst_mae_pct": round(metrics.worst_mae_pct, 2),
        "trades": metrics.trades,
    }
    return Scorecard(key=key, dsr=dsr, components=components)


def rank(scorecards) -> list:
    """Validated candidates, best DSR first."""
    return sorted(scorecards, key=lambda s: s.dsr, reverse=True)


def pareto_front(scorecards, dims) -> list:
    """Non-dominated set. `dims` = [(component_key, higher_is_better), ...]. A card is
    dominated if another is >= on every dim and strictly better on at least one."""
    def vec(s):
        return [(s.components.get(k) or 0.0) * (1 if hib else -1) for k, hib in dims]

    front = []
    for s in scorecards:
        vs = vec(s)
        dominated = any(
            o is not s
            and all(a <= b for a, b in zip(vs, vec(o)))
            and any(a < b for a, b in zip(vs, vec(o)))
            for o in scorecards
        )
        if not dominated:
            front.append(s)
    return front
