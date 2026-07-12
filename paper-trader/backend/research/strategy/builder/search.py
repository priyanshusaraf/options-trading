"""Bounded, deterministic composition generator — the bot proposing its own strategies.

The space is deliberately small and economically constrained (the anti-overfitting
principle): a directional TREND gate ANDed with a MOMENTUM trigger for entry, an optional
VOLATILITY quiet-bar gate, and mirrored short logic with reversion/trend-flip exits. Only
sensible pairings are enumerated — the generator never bolts arbitrary blocks together.

Every composition is constructed through `Composition.from_dict`, so it is grammar-valid
by the time it is returned, and `build_strategy` (emit → AST-validate → sandbox) is the
final proof it is safe to run. The trial count (compositions × folds) feeds the Deflated
Sharpe deflation downstream, so a wider search *raises* the significance bar rather than
manufacturing a winner.
"""
from __future__ import annotations

from research.strategy.builder.grammar import Composition

# Each entry: (long_trend, short_trend) mirror pair, keyed by a short code.
_TREND = {
    "emaSlope30": ("ema_slope_up(30, 5)", "ema_slope_down(30, 5)"),
    "emaSlope50": ("ema_slope_up(50, 5)", "ema_slope_down(50, 5)"),
    "priceEma50": ("price_above_ema(50)", "price_below_ema(50)"),
}
_MOMENTUM = {
    "zx10": ("zscore_cross_up(50, 1.0)", "zscore_cross_down(50, 1.0)"),
    "zx15": ("zscore_cross_up(50, 1.5)", "zscore_cross_down(50, 1.5)"),
    "roc10": ("roc_gt(10, 0.0)", "roc_lt(10, 0.0)"),
}
_VOL = {
    "": None,
    "quiet": "range_atr_lt(14, 2.5)",
}
# exits are shared: revert through the EMA (z back through 0) OR the trend flips
_LONG_EXIT = ["zscore_lt(50, 0.0)", "ema_slope_down(50, 5)"]
_SHORT_EXIT = ["zscore_gt(50, 0.0)", "ema_slope_up(50, 5)"]


def enumerate_compositions(limit: int = 24) -> list[Composition]:
    """Return up to `limit` grammar-valid compositions in a stable, deterministic order."""
    out: list[Composition] = []
    for tcode, (t_up, t_dn) in _TREND.items():
        for mcode, (m_up, m_dn) in _MOMENTUM.items():
            for vcode, vgate in _VOL.items():
                long_entry = [t_up, m_up] + ([vgate] if vgate else [])
                short_entry = [t_dn, m_dn] + ([vgate] if vgate else [])
                key = f"gen_{tcode}_{mcode}" + (f"_{vcode}" if vcode else "")
                out.append(Composition.from_dict({
                    "key": key,
                    "longEntry": {"all": long_entry},
                    "shortEntry": {"all": short_entry},
                    "longExit": {"any": list(_LONG_EXIT)},
                    "shortExit": {"any": list(_SHORT_EXIT)},
                }))
                if len(out) >= limit:
                    return out
    return out
