"""Trend Impulse V3 — the original EMA50 + displacement (z-score) strategy, now
exposed through the registry. This is a thin wrapper over `signals.compute_signals`,
which remains the single source of truth for the v3 math, so routing the engine /
backtest / chart through the registry is behaviour-preserving (see
tests/test_strategy_registry.py for the byte-for-byte golden check)."""
from __future__ import annotations

import pandas as pd

from app.strategy.signals import compute_signals

from .base import Strategy


class TrendImpulseV3(Strategy):
    key = "trend_impulse_v3"
    display_name = "Trend Impulse V3 (EMA-z)"
    default_params = {"ema_length": 50, "z_length": 50,
                      "entry_z": 1.0, "slope_lookback": 5}

    def compute(self, df: pd.DataFrame, ema_length: int = 50, z_length: int = 50,
                entry_z: float = 1.0, slope_lookback: int = 5) -> pd.DataFrame:
        return compute_signals(df, ema_length=ema_length, z_length=z_length,
                               entry_z=entry_z, slope_lookback=slope_lookback)


STRATEGY = TrendImpulseV3()
