"""Plain-language strategy explanation — so no research result is a black box.

A score you cannot interpret is a score you cannot trust with capital. `explain`
turns a (strategy_key, params) pair into a faithful, human-readable account of what
the strategy tries to do (thesis), which research primitives it draws on, and the
exact numbered rules — with the ACTUAL parameters that run used interpolated in — plus
a candid note of what the backtest does NOT model. The rule text is hand-authored
against the real signal math (`app/strategy/signals.py`, `expanding_z_v4.py`) so it can
never drift into a flattering fiction; the numbers are always the live ones.

Authored per strategy here (research-plane only); the execution strategies are never
touched. An unknown strategy degrades gracefully to a non-empty generic explanation so
a report never crashes for lack of prose.
"""
from __future__ import annotations

import dataclasses

from research.strategy.spec import definition


@dataclasses.dataclass
class StrategyExplanation:
    strategy_key: str
    display_name: str
    thesis: str
    primitives: list
    rules: list
    caveats: str


def _display_name(strategy_key: str) -> str:
    try:
        from research.evaluation import kernels
        return kernels.get_strategy(strategy_key).display_name or strategy_key
    except Exception:
        return strategy_key


def _trend_impulse_rules(p: dict) -> list:
    ema = p.get("ema_length", 50)
    zl = p.get("z_length", 50)
    ez = p.get("entry_z", 1.0)
    sl = p.get("slope_lookback", 5)
    return [
        f"Trend filter — EMA({ema}) of close; the trend is UP when that EMA is above its "
        f"own value {sl} bars ago, DOWN when below.",
        f"Displacement — z = (close − EMA) ÷ the {zl}-bar population standard deviation of "
        f"close: how many standard deviations price sits from its trend line.",
        f"Enter long — only in an up-trend, on the bar z crosses above +{ez} and is still "
        f"rising (a fresh, still-expanding breakout away from the trend).",
        f"Enter short — the mirror image: in a down-trend, z crosses below −{ez} with the "
        f"displacement widening.",
        "Exit long — z falls back below 0 (price has returned to its EMA) or the trend flips "
        "down; short exits mirror this. The edge is 'expired' once price re-converges.",
    ]


def _expanding_z_rules(p: dict) -> list:
    ema = p.get("ema_length", 50)
    zl = p.get("z_length", 50)
    atr = p.get("atr_length", 14)
    adapt = p.get("adapt_length", 200)
    ep = p.get("entry_pct", 65.0)
    xp = p.get("exit_pct", 35.0)
    mdd = p.get("min_drift_atr", 0.08)
    msa = p.get("max_signal_atr", 2.75)
    sl = p.get("slope_lookback", 5)
    return [
        f"Direction — EMA({ema}) whose slope over {sl} bars is normalized by ATR({atr}); the "
        f"trend is UP when that drift exceeds +{mdd} ATR, DOWN below −{mdd} ATR.",
        f"Displacement — z = (close − EMA) ÷ the {zl}-bar population stdev; the model acts on "
        f"|z|, the absolute displacement.",
        f"Adaptive threshold — an entry bar's |z| must clear the {ep:.0f}th percentile of |z| "
        f"over the last {adapt} bars (a self-calibrating breakout level that rises in choppy "
        f"regimes and falls in quiet ones); exits relax to the {xp:.0f}th percentile.",
        f"Expansion + quality gate — |z| must exceed the previous bar's (still expanding) and "
        f"the signal bar's range must be ≤ {msa} ATR, so climactic blow-off bars are skipped.",
        "Enter long — the impulse fires with z>0 and bullish drift; short is the mirror. Exit "
        "when the ATR-drift flips sign or price crosses back through the EMA.",
    ]


_AUTHORED = {
    "trend_impulse_v3": {
        "thesis": ("Price that breaks decisively away from its own trend line tends to keep "
                   "moving in the direction of that trend — momentum, filtered by trend so only "
                   "breakouts that agree with the prevailing drift are taken."),
        "rules": _trend_impulse_rules,
        "caveats": ("position size is 1 lot and P&L is additive; stops, targets and trailing are "
                    "the engine's risk overlay, not the strategy — the backtest measures the raw "
                    "signal edge."),
    },
    "expanding_z_v4": {
        "thesis": ("An adaptive-impulse trend model: rather than a fixed z threshold, it enters "
                   "when displacement breaks its own recent percentile band while still expanding "
                   "and the ATR-normalized trend agrees — capturing self-calibrating momentum "
                   "bursts and standing aside in noise."),
        "rules": _expanding_z_rules,
        "caveats": ("the strategy decides direction only; the backtest applies its ATR ratchet "
                    "overlay (initial ATR stop → Chandelier trail → MFE-capture floor). Size is 1 "
                    "lot, P&L additive; the base simulation has no slippage (a separate 2× "
                    "slippage-stress gate covers that)."),
    },
}


def explain(strategy_key: str, params: dict | None) -> StrategyExplanation:
    """Build a faithful explanation for `strategy_key` with `params` interpolated."""
    params = params or {}
    primitives = list(definition(strategy_key).primitives)
    authored = _AUTHORED.get(strategy_key)
    if authored is None:
        detail = (f"Parameters used: {params}." if params
                  else "No parameters were recorded for this run.")
        return StrategyExplanation(
            strategy_key=strategy_key, display_name=_display_name(strategy_key),
            thesis="No structured explanation is registered for this strategy yet.",
            primitives=primitives, rules=[detail],
            caveats="Add an entry to research/strategy/explain.py to describe this strategy.")
    return StrategyExplanation(
        strategy_key=strategy_key, display_name=_display_name(strategy_key),
        thesis=authored["thesis"], primitives=primitives,
        rules=authored["rules"](params), caveats=authored["caveats"])
