"""
Quant Engine — computes all quantitative metrics for a symbol or a portfolio.

Metrics computed:
  - Returns (simple + log)
  - Annualized volatility (rolling + static)
  - Beta vs benchmark
  - Correlation matrix
  - VaR (Historical + Parametric) at 95% and 99%
  - CVaR (Expected Shortfall)
  - Max Drawdown + Drawdown series
  - Sharpe / Sortino / Calmar ratios
  - Factor exposures: momentum, value, size, volatility
  - Composite quant score
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from backend.app.core.config import get_settings
from backend.app.core.logging import logger


TRADING_DAYS_PER_YEAR = 252


@dataclass
class QuantMetrics:
    symbol: str

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    annualized_vol: float = 0.0
    rolling_vol_30d: float = 0.0
    rolling_vol_90d: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Market
    beta: float = 1.0
    alpha: float = 0.0
    r_squared: float = 0.0
    correlation_with_benchmark: float = 0.0

    # VaR
    var_95_hist: float = 0.0   # Historical VaR (1-day, 95%)
    var_99_hist: float = 0.0
    var_95_param: float = 0.0  # Parametric VaR
    var_99_param: float = 0.0
    cvar_95: float = 0.0       # Conditional VaR (Expected Shortfall)

    # Drawdown
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration_days: int = 0

    # Factor exposures (–1 to +1)
    momentum_score: float = 0.0   # 12-1 month momentum
    volatility_score: float = 0.0  # inverse normalized vol (lower vol = higher score)
    size_score: float = 0.0        # proxy: log market cap rank
    value_score: float = 0.0       # from fundamentals

    # Composite
    composite_score: float = 0.0   # weighted combination of all factors

    # Extras
    skewness: float = 0.0
    kurtosis: float = 0.0
    observations: int = 0

    raw_returns: pd.Series = field(default_factory=pd.Series, repr=False)


class QuantEngine:
    """
    Stateless engine. Pass OHLCV DataFrames in, get QuantMetrics out.
    """

    def __init__(self):
        self.risk_free_rate = get_settings().risk_free_rate
        self.rf_daily = (1 + self.risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1

    # ── Main entry point ──────────────────────────────────────────────────────

    def compute(
        self,
        symbol: str,
        price_df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame] = None,
        market_cap: Optional[float] = None,
        pe_ratio: Optional[float] = None,
    ) -> QuantMetrics:
        """
        price_df: DataFrame with at least a 'close' column, date-indexed.
        benchmark_df: Same format. If None, beta/alpha not computed.
        """
        if price_df.empty or len(price_df) < 20:
            logger.warning(f"[QuantEngine] Insufficient data for {symbol} ({len(price_df)} rows)")
            return QuantMetrics(symbol=symbol)

        closes = price_df["close"].dropna()
        returns = closes.pct_change().dropna()
        log_returns = np.log(closes / closes.shift(1)).dropna()
        n = len(returns)

        m = QuantMetrics(symbol=symbol, raw_returns=returns, observations=n)

        # ── Returns ───────────────────────────────────────────────────────────
        m.total_return = float((closes.iloc[-1] / closes.iloc[0]) - 1)
        years = n / TRADING_DAYS_PER_YEAR
        m.annualized_return = float((1 + m.total_return) ** (1 / max(years, 0.01)) - 1)

        # ── Volatility ────────────────────────────────────────────────────────
        m.annualized_vol = float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
        m.rolling_vol_30d = self._rolling_vol(returns, 30)
        m.rolling_vol_90d = self._rolling_vol(returns, 90)

        # ── Return distribution stats ─────────────────────────────────────────
        m.skewness = float(stats.skew(returns))
        m.kurtosis = float(stats.kurtosis(returns))

        # ── Risk-adjusted ratios ──────────────────────────────────────────────
        excess = returns - self.rf_daily
        m.sharpe_ratio = self._sharpe(returns)
        m.sortino_ratio = self._sortino(returns)
        m.calmar_ratio = self._calmar(returns, m)

        # ── Beta & Alpha vs benchmark ─────────────────────────────────────────
        if benchmark_df is not None and not benchmark_df.empty:
            bmark_closes = benchmark_df["close"].dropna()
            bmark_returns = bmark_closes.pct_change().dropna()
            # Align on common dates
            aligned = pd.DataFrame({"asset": returns, "benchmark": bmark_returns}).dropna()
            if len(aligned) >= 20:
                m.beta, m.alpha, m.r_squared, m.correlation_with_benchmark = self._beta_alpha(
                    aligned["asset"], aligned["benchmark"]
                )

        # ── Value at Risk ─────────────────────────────────────────────────────
        m.var_95_hist, m.var_99_hist = self._historical_var(returns)
        m.var_95_param, m.var_99_param = self._parametric_var(returns)
        m.cvar_95 = self._cvar(returns, 0.05)

        # ── Drawdown ──────────────────────────────────────────────────────────
        dd_series = self._drawdown_series(closes)
        m.max_drawdown = float(dd_series.min())
        m.current_drawdown = float(dd_series.iloc[-1])
        m.avg_drawdown = float(dd_series[dd_series < 0].mean()) if (dd_series < 0).any() else 0.0
        m.drawdown_duration_days = self._drawdown_duration(dd_series)

        # ── Factor Exposures ──────────────────────────────────────────────────
        m.momentum_score = self._momentum_factor(closes)
        m.volatility_score = self._volatility_factor(returns)
        if market_cap is not None:
            m.size_score = self._size_factor_proxy(market_cap)
        if pe_ratio is not None:
            m.value_score = self._value_factor(pe_ratio)

        # ── Composite Score ───────────────────────────────────────────────────
        m.composite_score = self._composite(m)

        return m

    # ── Correlation matrix ────────────────────────────────────────────────────

    def correlation_matrix(
        self,
        prices: pd.DataFrame,
        window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        prices: wide DataFrame, each column is a symbol.
        window: if provided, compute rolling correlation over last N days.
        """
        returns = prices.pct_change().dropna()
        if window:
            returns = returns.tail(window)
        return returns.corr()

    def rolling_correlation(
        self,
        series_a: pd.Series,
        series_b: pd.Series,
        window: int = 60,
    ) -> pd.Series:
        """Rolling pairwise correlation between two return series."""
        ra = series_a.pct_change().dropna()
        rb = series_b.pct_change().dropna()
        aligned = pd.DataFrame({"a": ra, "b": rb}).dropna()
        return aligned["a"].rolling(window).corr(aligned["b"])

    # ── Private helpers ───────────────────────────────────────────────────────

    def _rolling_vol(self, returns: pd.Series, window: int) -> float:
        if len(returns) < window:
            return float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
        return float(returns.tail(window).std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    def _sharpe(self, returns: pd.Series) -> float:
        excess = returns - self.rf_daily
        std = excess.std()
        if std == 0:
            return 0.0
        return float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))

    def _sortino(self, returns: pd.Series) -> float:
        excess = returns - self.rf_daily
        downside = excess[excess < 0]
        if len(downside) == 0:
            return float("inf")
        downside_std = downside.std()
        if downside_std == 0:
            return 0.0
        return float(excess.mean() / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR))

    def _calmar(self, returns: pd.Series, m: QuantMetrics) -> float:
        if m.max_drawdown == 0:
            return 0.0
        return float(m.annualized_return / abs(m.max_drawdown))

    def _beta_alpha(
        self,
        asset_returns: pd.Series,
        bmark_returns: pd.Series,
    ) -> tuple[float, float, float, float]:
        slope, intercept, r_value, _, _ = stats.linregress(bmark_returns, asset_returns)
        beta = float(slope)
        alpha = float(intercept * TRADING_DAYS_PER_YEAR)
        r_squared = float(r_value**2)
        correlation = float(r_value)
        return beta, alpha, r_squared, correlation

    def _historical_var(self, returns: pd.Series) -> tuple[float, float]:
        sorted_r = returns.sort_values()
        var_95 = float(np.percentile(sorted_r, 5))
        var_99 = float(np.percentile(sorted_r, 1))
        return var_95, var_99

    def _parametric_var(self, returns: pd.Series) -> tuple[float, float]:
        mu = returns.mean()
        sigma = returns.std()
        var_95 = float(stats.norm.ppf(0.05, mu, sigma))
        var_99 = float(stats.norm.ppf(0.01, mu, sigma))
        return var_95, var_99

    def _cvar(self, returns: pd.Series, alpha: float = 0.05) -> float:
        """Expected Shortfall: mean of returns below VaR threshold."""
        threshold = np.percentile(returns, alpha * 100)
        tail = returns[returns <= threshold]
        return float(tail.mean()) if len(tail) > 0 else float(threshold)

    def _drawdown_series(self, prices: pd.Series) -> pd.Series:
        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max
        return drawdown

    def _drawdown_duration(self, dd_series: pd.Series) -> int:
        """Current uninterrupted drawdown duration in trading days."""
        in_dd = (dd_series < 0)
        if not in_dd.iloc[-1]:
            return 0
        count = 0
        for val in reversed(in_dd.values):
            if val:
                count += 1
            else:
                break
        return count

    def _momentum_factor(self, prices: pd.Series) -> float:
        """12-1 month momentum (skip last month to avoid short-term reversal)."""
        if len(prices) < 252:
            return 0.0
        price_12m_ago = prices.iloc[-252]
        price_1m_ago = prices.iloc[-21]
        if price_12m_ago == 0:
            return 0.0
        ret_12m = float((price_1m_ago / price_12m_ago) - 1)
        # Normalize to -1..+1 using tanh
        return float(np.tanh(ret_12m * 2))

    def _volatility_factor(self, returns: pd.Series) -> float:
        """
        Low-volatility factor: lower volatility = higher score.
        Normalized so typical ~20% annual vol maps to 0.
        """
        ann_vol = float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
        # Score is inverse: vol=10% → +0.5, vol=30% → -0.5 roughly
        return float(np.tanh((0.20 - ann_vol) * 5))

    def _size_factor_proxy(self, market_cap: float) -> float:
        """
        Small-cap premium proxy. log(market_cap) normalized.
        Reference: log(1B INR) ≈ 20.7, log(1T INR) ≈ 27.6
        Returns –1 (large cap) to +1 (small cap).
        """
        if market_cap <= 0:
            return 0.0
        log_cap = np.log(market_cap)
        # Invert: small cap gets higher score
        score = (25 - log_cap) / 5
        return float(np.clip(score, -1, 1))

    def _value_factor(self, pe_ratio: float) -> float:
        """Lower P/E = higher value score. Typical P/E range 10–40."""
        if pe_ratio <= 0:
            return 0.0
        score = (25 - pe_ratio) / 20
        return float(np.clip(score, -1, 1))

    def _composite(self, m: QuantMetrics) -> float:
        """
        Weighted composite score combining all factors.
        Weights reflect importance for a medium-term equity strategy.
        """
        weights = {
            "momentum": 0.30,
            "volatility": 0.20,
            "value": 0.20,
            "size": 0.10,
            "sharpe": 0.20,
        }
        # Normalize Sharpe to -1..+1
        sharpe_norm = float(np.tanh(m.sharpe_ratio / 3))

        raw = (
            weights["momentum"] * m.momentum_score
            + weights["volatility"] * m.volatility_score
            + weights["value"] * m.value_score
            + weights["size"] * m.size_score
            + weights["sharpe"] * sharpe_norm
        )
        return float(np.clip(raw, -1, 1))
