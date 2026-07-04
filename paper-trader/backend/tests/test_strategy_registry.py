"""The registry is the seam the whole multi-strategy platform hangs off, so two
things are pinned here: (1) the registry's `trend_impulse_v3` produces output
BYTE-IDENTICAL to the legacy `compute_signals` (no behaviour change when we route
the engine/backtest/chart through the registry), and (2) every registered strategy
honours the canonical four-column contract on real-shaped data."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.signals import compute_signals
from app.strategy.registry import (
    get_strategy, all_strategies, strategy_keys, DEFAULT_STRATEGY_KEY)
from app.strategy.registry.base import CANONICAL_COLUMNS


def _synthetic(n: int = 400) -> pd.DataFrame:
    """Deterministic OHLC: a drifting sine so EMA slope and z-score both swing
    through entries and exits. Fixed seed → stable golden comparison."""
    rng = np.random.default_rng(42)
    t = np.arange(n)
    base = 1000.0 + 60.0 * np.sin(t / 18.0) + 0.4 * t
    noise = rng.normal(0, 4.0, n)
    close = base + noise
    high = close + np.abs(rng.normal(0, 3.0, n))
    low = close - np.abs(rng.normal(0, 3.0, n))
    open_ = close + rng.normal(0, 2.0, n)
    dates = pd.date_range("2024-01-01 09:15", periods=n, freq="15min")
    return pd.DataFrame({"date": dates, "open": open_, "high": high,
                         "low": low, "close": close})


def test_default_key_is_v3():
    assert DEFAULT_STRATEGY_KEY == "trend_impulse_v3"
    assert get_strategy(None).key == "trend_impulse_v3"
    assert get_strategy("does_not_exist").key == "trend_impulse_v3"  # safe fallback


def test_v3_registered_and_listed():
    keys = strategy_keys()
    assert "trend_impulse_v3" in keys
    assert all(s.display_name for s in all_strategies())  # every strategy is labelled


def test_v3_registry_matches_legacy_compute_signals_byte_for_byte():
    df = _synthetic()
    legacy = compute_signals(df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    viareg = get_strategy("trend_impulse_v3").signals(
        df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    # canonical signal columns identical
    for col in CANONICAL_COLUMNS:
        assert (legacy[col].fillna(False) == viareg[col].fillna(False)).all(), col
    # key indicator columns identical too (chart payload depends on these)
    for col in ("ema", "z", "slope"):
        pd.testing.assert_series_equal(legacy[col], viareg[col], check_names=False)


def test_v3_defaults_applied_when_no_overrides():
    df = _synthetic()
    explicit = get_strategy("trend_impulse_v3").signals(
        df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    defaulted = get_strategy("trend_impulse_v3").signals(df)  # uses default_params
    for col in CANONICAL_COLUMNS:
        assert (explicit[col].fillna(False) == defaulted[col].fillna(False)).all(), col


def test_every_strategy_emits_canonical_columns():
    df = _synthetic()
    for strat in all_strategies():
        out = strat.signals(df)
        for col in CANONICAL_COLUMNS:
            assert col in out.columns, f"{strat.key} missing {col}"
            assert out[col].dropna().isin([True, False]).all(), f"{strat.key}:{col} not boolean"
