"""Common contract every strategy implements so the engine, backtest, and chart
layers can treat them interchangeably.

A strategy turns a candle DataFrame into the canonical four boolean columns the
rest of the system already understands:

    longEntry, shortEntry, longExit, shortExit

It MAY emit extra indicator columns (ema, z, atr, …) — chart payloads use those
for whichever strategy a chart is rendering — but the four canonical columns are
mandatory. Direction/stop/target sizing is NOT the strategy's job; the engine owns
the risk layer (premium stop/target, trailing). A strategy only decides *when* to
be long/short and *when* its own edge has expired.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

CANONICAL_COLUMNS = ("longEntry", "shortEntry", "longExit", "shortExit")


class Strategy:
    """Base class. Subclasses set `key`, `display_name`, `default_params` and
    implement `compute`. Call `signals()` (not `compute()` directly) so default
    params are applied and the canonical-column contract is enforced."""

    key: str = ""
    display_name: str = ""
    default_params: dict[str, Any] = {}
    # Optional trade-management declaration for the BACKTEST ratchet overlay
    # (initial ATR stop -> Chandelier trail -> MFE-capture floor). None = the
    # strategy exits on its canonical flags only. Keys (all required if set):
    # atr_length, initial_risk_atr, trail_start_r, trail_atr,
    # use_mfe_capture_floor, capture_start_r, capture_pct.
    risk_model: dict[str, Any] | None = None

    def compute(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        raise NotImplementedError

    def signals(self, df: pd.DataFrame, **overrides: Any) -> pd.DataFrame:
        """Merge caller overrides (None values ignored) over `default_params`,
        run `compute`, and verify the canonical columns are present."""
        params = dict(self.default_params)
        params.update({k: v for k, v in overrides.items() if v is not None})
        out = self.compute(df, **params)
        missing = [c for c in CANONICAL_COLUMNS if c not in out.columns]
        if missing:
            raise ValueError(f"strategy {self.key!r} did not emit columns: {missing}")
        return out
