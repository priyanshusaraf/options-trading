"""
Market Regime Detector.

Detects four regimes using rule-based statistical analysis:
  1. BULL_TREND     — rising prices, low vol, positive momentum
  2. BEAR_TREND     — falling prices, rising vol
  3. HIGH_VOL       — volatility spike (VIX-like)
  4. MEAN_REVERTING — range-bound, low ADX

Each regime adjusts how signals are weighted in the Decision Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from backend.app.core.logging import logger


class Regime(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    HIGH_VOL = "HIGH_VOL"
    MEAN_REVERTING = "MEAN_REVERTING"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeResult:
    regime: Regime
    confidence: float          # 0–1
    vol_regime: str            # "low" / "normal" / "high" / "extreme"
    trend_strength: float      # 0–1 (from ADX equivalent)
    is_trending: bool
    is_mean_reverting: bool
    realized_vol_30d: float
    realized_vol_90d: float
    description: str

    # Regime-specific signal multipliers (used by Decision Engine)
    momentum_weight_adj: float = 1.0
    mean_reversion_weight_adj: float = 1.0
    vol_risk_discount: float = 1.0


TRADING_DAYS = 252


class RegimeDetector:
    """
    Detects regime using benchmark/index price data.
    Pass Nifty50 or S&P500 OHLCV DataFrame.
    """

    def detect(self, df: pd.DataFrame) -> RegimeResult:
        if len(df) < 60:
            return RegimeResult(
                regime=Regime.UNKNOWN,
                confidence=0.0,
                vol_regime="unknown",
                trend_strength=0.0,
                is_trending=False,
                is_mean_reverting=False,
                realized_vol_30d=0.0,
                realized_vol_90d=0.0,
                description="Insufficient data for regime detection.",
            )

        closes = df["close"].dropna()
        returns = closes.pct_change().dropna()

        # ── Volatility analysis ────────────────────────────────────────────────
        vol_30d = float(returns.tail(30).std() * np.sqrt(TRADING_DAYS))
        vol_90d = float(returns.tail(90).std() * np.sqrt(TRADING_DAYS))
        vol_1y = float(returns.tail(252).std() * np.sqrt(TRADING_DAYS)) if len(returns) >= 252 else vol_90d

        vol_regime = self._classify_vol(vol_30d, vol_1y)

        # ── Trend analysis (rolling Z-score of returns) ────────────────────────
        ma_50 = closes.rolling(50).mean()
        ma_200 = closes.rolling(200).mean() if len(closes) >= 200 else closes.rolling(50).mean()

        last_close = float(closes.iloc[-1])
        last_ma50 = float(ma_50.iloc[-1])
        last_ma200 = float(ma_200.iloc[-1])

        above_ma50 = last_close > last_ma50
        above_ma200 = last_close > last_ma200
        ma_aligned = last_ma50 > last_ma200  # Bullish alignment

        # Trend strength via linear regression R² over 60 days
        trend_strength = self._trend_r_squared(closes.tail(60))

        # ── Mean reversion test (Hurst exponent approximation) ───────────────
        hurst = self._hurst_exponent(closes.tail(90))
        is_mean_reverting = hurst < 0.45
        is_trending = hurst > 0.55

        # ── Momentum ─────────────────────────────────────────────────────────
        mom_30d = float((closes.iloc[-1] / closes.iloc[-30]) - 1) if len(closes) >= 30 else 0.0
        mom_90d = float((closes.iloc[-1] / closes.iloc[-90]) - 1) if len(closes) >= 90 else 0.0

        # ── Regime classification ─────────────────────────────────────────────
        regime, confidence = self._classify_regime(
            vol_regime, above_ma50, above_ma200, ma_aligned,
            is_trending, is_mean_reverting, mom_30d
        )

        # ── Signal multipliers per regime ─────────────────────────────────────
        multipliers = self._regime_multipliers(regime, vol_regime)

        return RegimeResult(
            regime=regime,
            confidence=confidence,
            vol_regime=vol_regime,
            trend_strength=trend_strength,
            is_trending=is_trending,
            is_mean_reverting=is_mean_reverting,
            realized_vol_30d=vol_30d,
            realized_vol_90d=vol_90d,
            description=self._describe(regime, vol_regime, mom_30d, hurst),
            **multipliers,
        )

    # ── Classification helpers ────────────────────────────────────────────────

    def _classify_vol(self, vol_30d: float, vol_1y: float) -> str:
        ratio = vol_30d / vol_1y if vol_1y > 0 else 1.0
        if ratio > 2.0 or vol_30d > 0.40:
            return "extreme"
        if ratio > 1.5 or vol_30d > 0.25:
            return "high"
        if ratio < 0.6 or vol_30d < 0.10:
            return "low"
        return "normal"

    def _classify_regime(
        self,
        vol_regime: str,
        above_ma50: bool,
        above_ma200: bool,
        ma_aligned: bool,
        is_trending: bool,
        is_mean_reverting: bool,
        mom_30d: float,
    ) -> tuple[Regime, float]:
        if vol_regime in ("extreme", "high") and mom_30d < -0.05:
            return Regime.HIGH_VOL, 0.85

        if above_ma50 and above_ma200 and ma_aligned and mom_30d > 0:
            conf = 0.7 + 0.2 * (mom_30d > 0.05)
            return Regime.BULL_TREND, min(conf, 0.95)

        if not above_ma50 and not above_ma200 and mom_30d < -0.03:
            return Regime.BEAR_TREND, 0.75

        if is_mean_reverting and vol_regime in ("low", "normal"):
            return Regime.MEAN_REVERTING, 0.70

        # Fallback: mixed signals
        if mom_30d > 0:
            return Regime.BULL_TREND, 0.45
        return Regime.BEAR_TREND, 0.45

    def _trend_r_squared(self, prices: pd.Series) -> float:
        """Linear regression R² as trend strength measure."""
        try:
            x = np.arange(len(prices))
            y = prices.values
            corr = np.corrcoef(x, y)[0, 1]
            return float(corr**2)
        except Exception:
            return 0.0

    def _hurst_exponent(self, prices: pd.Series, lags: int = 20) -> float:
        """
        Simplified Hurst exponent estimate.
        H > 0.5: trending, H < 0.5: mean-reverting, H ≈ 0.5: random walk.
        """
        try:
            log_prices = np.log(prices.values)
            ts = []
            for lag in range(2, min(lags, len(log_prices) // 2)):
                diffs = np.diff(log_prices, lag)
                ts.append(np.std(diffs))
            if len(ts) < 3:
                return 0.5
            lags_arr = np.arange(2, 2 + len(ts))
            log_lags = np.log(lags_arr)
            log_ts = np.log(ts)
            h = np.polyfit(log_lags, log_ts, 1)[0]
            return float(np.clip(h, 0, 1))
        except Exception:
            return 0.5

    def _regime_multipliers(self, regime: Regime, vol_regime: str) -> dict:
        """
        Return weight adjustments for the Decision Engine.
        In trending regimes, momentum signals are more reliable.
        In mean-reverting, oversold/overbought signals matter more.
        High vol → reduce position sizing across the board.
        """
        if regime == Regime.BULL_TREND:
            return {"momentum_weight_adj": 1.4, "mean_reversion_weight_adj": 0.7, "vol_risk_discount": 1.0}
        if regime == Regime.BEAR_TREND:
            return {"momentum_weight_adj": 0.6, "mean_reversion_weight_adj": 1.2, "vol_risk_discount": 0.7}
        if regime == Regime.HIGH_VOL:
            return {"momentum_weight_adj": 0.5, "mean_reversion_weight_adj": 0.5, "vol_risk_discount": 0.4}
        if regime == Regime.MEAN_REVERTING:
            return {"momentum_weight_adj": 0.7, "mean_reversion_weight_adj": 1.5, "vol_risk_discount": 1.0}
        return {"momentum_weight_adj": 1.0, "mean_reversion_weight_adj": 1.0, "vol_risk_discount": 1.0}

    def _describe(self, regime: Regime, vol: str, mom: float, hurst: float) -> str:
        templates = {
            Regime.BULL_TREND: f"Market is in a bull trend (Hurst={hurst:.2f}). Momentum strategies preferred. Vol: {vol}.",
            Regime.BEAR_TREND: f"Market is in a bear trend. Defensive posture recommended. 30d return: {mom:.1%}.",
            Regime.HIGH_VOL: f"Elevated volatility detected (vol regime: {vol}). Reduce position sizes.",
            Regime.MEAN_REVERTING: f"Market is range-bound (Hurst={hurst:.2f}). Mean-reversion signals more reliable.",
            Regime.UNKNOWN: "Insufficient data to classify regime.",
        }
        return templates.get(regime, "Unknown regime.")
