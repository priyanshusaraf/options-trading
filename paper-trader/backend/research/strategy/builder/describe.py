"""Faithful plain-language explanation of a generated strategy.

Because a Composition is built from a fixed vocabulary of vetted blocks, its
explanation can be generated exactly — every rule maps to a named block with its real
parameters, so the prose can never drift into a flattering fiction (the standing risk
with any auto-generated strategy). Reuses the `StrategyExplanation` shape the rest of
the research plane already renders.
"""
from __future__ import annotations

from research.strategy.builder.blocks import BLOCKS
from research.strategy.builder.grammar import BlockRef, Clause, Composition
from research.strategy.explain import StrategyExplanation

_GROUP_LABEL = {"trend": "Trend", "momentum": "Momentum",
                "volatility": "Volatility", "confirmation": "Confirmation"}

# One plain-language template per block; args are the block's real parameters.
_DESCRIBE = {
    "ema_slope_up":     lambda a: f"EMA({a[0]}) is rising (above its value {a[1]} bars ago)",
    "ema_slope_down":   lambda a: f"EMA({a[0]}) is falling (below its value {a[1]} bars ago)",
    "price_above_ema":  lambda a: f"price is above EMA({a[0]})",
    "price_below_ema":  lambda a: f"price is below EMA({a[0]})",
    "zscore_gt":        lambda a: f"the z-score (vs EMA {a[0]}) is above {a[1]}",
    "zscore_lt":        lambda a: f"the z-score (vs EMA {a[0]}) is below {a[1]}",
    "zscore_cross_up":  lambda a: f"the z-score (vs EMA {a[0]}) crosses up through +{a[1]}",
    "zscore_cross_down": lambda a: f"the z-score (vs EMA {a[0]}) crosses down through −{a[1]}",
    "roc_gt":           lambda a: f"the {a[0]}-bar rate-of-change is above {a[1]}",
    "roc_lt":           lambda a: f"the {a[0]}-bar rate-of-change is below {a[1]}",
    "atr_pct_lt":       lambda a: f"ATR({a[0]}) is under {a[1]}% of price (quiet-bar gate)",
    "range_atr_lt":     lambda a: f"the bar's range is under {a[1]}×ATR({a[0]})",
    "still_expanding_z": lambda a: f"the |z-score| (vs EMA {a[0]}) is still widening vs the prior bar",
}


def describe_ref(ref: BlockRef) -> str:
    tmpl = _DESCRIBE.get(ref.name)
    return tmpl(ref.args) if tmpl else f"{ref.name}{ref.args}"


def _describe_clause(clause: Clause) -> str:
    parts = [describe_ref(r) for r in clause.refs]
    if len(parts) == 1:
        return parts[0]
    joiner = "; and " if clause.op == "all" else "; or "
    lead = "ALL of — " if clause.op == "all" else "ANY of — "
    return lead + joiner.join(parts)


def _primitives(comp: Composition) -> list:
    seen, out = set(), []
    for ref in comp.block_refs():
        label = _GROUP_LABEL.get(BLOCKS[ref.name].group, BLOCKS[ref.name].group)
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def explain_composition(comp: Composition) -> StrategyExplanation:
    rules = [
        f"Enter long — {_describe_clause(comp.long_entry)}.",
        f"Enter short — {_describe_clause(comp.short_entry)}.",
        f"Exit long — {_describe_clause(comp.long_exit)}.",
        f"Exit short — {_describe_clause(comp.short_exit)}.",
    ]
    thesis = ("A machine-composed strategy: it was assembled by the constrained primitive "
              "builder from a fixed vocabulary of vetted, unit-tested blocks — so every rule "
              "below maps exactly to named indicator math, with the real parameters shown.")
    caveats = ("Generated code, composed only of whitelisted blocks and statically validated "
               "against an AST allow-list before it can run. Position size is 1 lot and P&L is "
               "additive; the backtest measures the raw signal edge (stops/targets/trailing are "
               "the engine's separate risk overlay).")
    return StrategyExplanation(
        strategy_key=comp.key, display_name=comp.key, thesis=thesis,
        primitives=_primitives(comp), rules=rules, caveats=caveats)


def explanation_for(strategy, params: dict) -> StrategyExplanation:
    """Dispatch: a generated strategy is explained from its composition (exact); any
    other strategy routes through the authored/curated `explain`."""
    comp = getattr(strategy, "composition", None)
    if comp is not None:
        return explain_composition(comp)
    from research.strategy.explain import explain
    return explain(strategy.key, params)
