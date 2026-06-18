"""
Tests for the Quant Engine.
Run with: pytest backend/tests/test_quant_engine.py -v
"""
import numpy as np
import pandas as pd
import pytest

from backend.app.analytics.quant.engine import QuantEngine, QuantMetrics


def _make_price_df(n: int = 500, trend: float = 0.0003, vol: float = 0.015, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV price data for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    returns = rng.normal(trend, vol, n)
    close = 100 * np.exp(np.cumsum(returns))
    high = close * (1 + abs(rng.normal(0, 0.005, n)))
    low = close * (1 - abs(rng.normal(0, 0.005, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(100000, 5000000, n)},
        index=dates,
    )
    return df


@pytest.fixture
def engine():
    return QuantEngine()


@pytest.fixture
def price_df():
    return _make_price_df()


@pytest.fixture
def benchmark_df():
    return _make_price_df(seed=99, trend=0.0002)


class TestQuantEngine:
    def test_compute_returns_metrics(self, engine, price_df):
        m = engine.compute("TEST", price_df)
        assert isinstance(m, QuantMetrics)
        assert m.observations > 0
        assert isinstance(m.annualized_return, float)
        assert isinstance(m.annualized_vol, float)

    def test_vol_positive(self, engine, price_df):
        m = engine.compute("TEST", price_df)
        assert m.annualized_vol > 0

    def test_var_ordering(self, engine, price_df):
        """VaR at 99% must be more negative than at 95%."""
        m = engine.compute("TEST", price_df)
        assert m.var_99_hist <= m.var_95_hist

    def test_cvar_more_extreme_than_var(self, engine, price_df):
        """CVaR must be <= VaR (deeper tail)."""
        m = engine.compute("TEST", price_df)
        assert m.cvar_95 <= m.var_95_hist

    def test_max_drawdown_non_positive(self, engine, price_df):
        m = engine.compute("TEST", price_df)
        assert m.max_drawdown <= 0

    def test_sharpe_with_positive_trend(self):
        """A clearly upward-trending series should have positive Sharpe."""
        df = _make_price_df(trend=0.001, vol=0.010, n=500)
        engine = QuantEngine()
        m = engine.compute("BULL", df)
        assert m.sharpe_ratio > 0

    def test_beta_computed_with_benchmark(self, engine, price_df, benchmark_df):
        m = engine.compute("TEST", price_df, benchmark_df=benchmark_df)
        assert m.beta != 0.0
        assert m.r_squared >= 0
        assert m.r_squared <= 1

    def test_composite_score_range(self, engine, price_df):
        m = engine.compute("TEST", price_df)
        assert -1 <= m.composite_score <= 1

    def test_factor_scores_range(self, engine, price_df):
        m = engine.compute("TEST", price_df)
        for score in [m.momentum_score, m.volatility_score]:
            assert -1 <= score <= 1

    def test_empty_df_returns_empty_metrics(self, engine):
        m = engine.compute("EMPTY", pd.DataFrame())
        assert m.observations == 0
        assert m.composite_score == 0.0

    def test_insufficient_data_returns_defaults(self, engine):
        df = _make_price_df(n=10)
        m = engine.compute("SHORT", df)
        assert m.composite_score == 0.0

    def test_correlation_matrix(self, engine):
        symbols = ["A", "B", "C"]
        prices = pd.DataFrame(
            {s: _make_price_df(seed=i)["close"] for i, s in enumerate(symbols)}
        )
        corr = engine.correlation_matrix(prices)
        assert corr.shape == (3, 3)
        # Diagonal must be 1
        for s in symbols:
            assert abs(corr.loc[s, s] - 1.0) < 1e-10
        # Symmetric
        assert abs(corr.loc["A", "B"] - corr.loc["B", "A"]) < 1e-10

    def test_rolling_correlation(self, engine):
        df_a = _make_price_df(seed=1)
        df_b = _make_price_df(seed=2)
        roll_corr = engine.rolling_correlation(df_a["close"], df_b["close"], window=60)
        assert len(roll_corr) > 0
        assert roll_corr.dropna().between(-1, 1).all()
