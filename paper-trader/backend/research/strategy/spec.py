"""Strategy definitions: primitive-taxonomy tags + a bounded, constrained search
space, declared beside (not inside) the execution strategies.

This is the M1 resolution of the "semantic strategy" goal: the primitive taxonomy is
carried as descriptive *tags* (which seeds the future builder and drives UI grouping),
while the strategy itself stays an opaque `compute(df, **params)`. Executable
swappable slots + a slot->signal combination grammar are the LAST milestone (M5); we
do not commit to that shape here. What optimization actually needs now is the
`param_space` (search values + cross-field validity), and that is all this declares.
"""
from __future__ import annotations

import dataclasses
import itertools


@dataclasses.dataclass
class ParamSpec:
    name: str
    kind: str                    # int | float | bool | categorical
    default: object
    values: list | None = None   # discrete search values; None/empty => not searched
    optimizable: bool = True


@dataclasses.dataclass
class StrategyDefinition:
    key: str
    primitives: list             # taxonomy tags, e.g. ["Trend", "MeanReversion"]
    params: dict                 # name -> ParamSpec


# Hand-declared for the two existing strategies. Ranges are deliberately COARSE and
# small (optimization must stay constrained — no unbounded complexity). Params not
# listed as searched fall back to the strategy's own defaults in the backtest.
_DEFINITIONS: dict[str, StrategyDefinition] = {
    "trend_impulse_v3": StrategyDefinition(
        key="trend_impulse_v3",
        primitives=["Trend", "MeanReversion", "Confirmation"],
        params={
            "ema_length": ParamSpec("ema_length", "int", 50, values=[30, 50, 70]),
            "z_length": ParamSpec("z_length", "int", 50, values=[30, 50]),
            "entry_z": ParamSpec("entry_z", "float", 1.0, values=[0.75, 1.0, 1.5]),
            "slope_lookback": ParamSpec("slope_lookback", "int", 5, values=None,
                                        optimizable=False),
        }),
    "expanding_z_v4": StrategyDefinition(
        key="expanding_z_v4",
        primitives=["Trend", "MeanReversion", "Volatility", "Confirmation"],
        params={
            "ema_length": ParamSpec("ema_length", "int", 50, values=[30, 50, 70]),
            "entry_pct": ParamSpec("entry_pct", "float", 65.0, values=[60.0, 65.0, 70.0]),
            "exit_pct": ParamSpec("exit_pct", "float", 35.0, values=[30.0, 35.0]),
        }),
}

# Cross-field validity constraints (per strategy). The optimizer skips invalid points
# rather than burning an evaluation on them.
_CONSTRAINTS = {
    "expanding_z_v4": [lambda p: p.get("exit_pct", 0) < p.get("entry_pct", 1e9)],
}


def definition(strategy_key: str) -> StrategyDefinition:
    return _DEFINITIONS.get(strategy_key,
                            StrategyDefinition(strategy_key, [], {}))


def param_space(strategy_key: str) -> dict:
    return definition(strategy_key).params


def grid(space: dict) -> list:
    """Cartesian product over the optimizable params that declare search values.
    Empty space -> a single empty point (i.e. use strategy defaults)."""
    keys = [k for k, s in space.items() if s.optimizable and s.values]
    if not keys:
        return [{}]
    return [dict(zip(keys, combo))
            for combo in itertools.product(*[space[k].values for k in keys])]


def is_valid(strategy_key: str, params: dict) -> bool:
    return all(check(params) for check in _CONSTRAINTS.get(strategy_key, []))
