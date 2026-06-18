"""
Technical Analysis Engine.

Computes indicators: RSI, MACD, Bollinger Bands, Moving Averages, ATR, ADX.
Detects: breakouts, trend reversals, golden/death crosses.
Returns probabilistic signals (0–1), not binary buy/sell.

Probability model: weighted combination of confirming indicator readings,
normalized through a sigmoid function. NOT ML — purely rule-based with
uncertainty quantification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import ta

from backend.app.core.logging import logger


@dataclass
class TechnicalSignals:
    symbol: str

    # Indicators (latest values)
    rsi_14: float = 50.0
    rsi_7: float = 50.0

    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    macd_crossover: str = "none"   # "bullish" / "bearish" / "none"

    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_middle: float = 0.0
    bb_pct: float = 0.5            # Position within band: 0=lower, 1=upper
    bb_width: float = 0.0          # Bandwidth (normalized)

    ma_20: float = 0.0
    ma_50: float = 0.0
    ma_200: float = 0.0
    ma_cross: str = "none"         # "golden" / "death" / "none"

    atr_14: float = 0.0            # Average True Range
    adx_14: float = 0.0            # Average Directional Index (trend strength)

    # Probabilistic signals (0–1)
    bullish_prob: float = 0.5
    bearish_prob: float = 0.5
    breakout_prob: float = 0.0
    reversal_prob: float = 0.0
    trend_strength: float = 0.0    # 0=choppy, 1=strong trend

    # Human-readable signal
    signal: str = "NEUTRAL"        # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    confidence: float = 0.0        # 0–1


class TechnicalEngine:
    """
    Stateless technical analysis engine.
    Pass an OHLCV DataFrame, get TechnicalSignals back.
    """

    MIN_ROWS = 50

    def compute(self, symbol: str, df: pd.DataFrame) -> TechnicalSignals:
        if df.empty or len(df) < self.MIN_ROWS:
            logger.warning(f"[TechEngine] Insufficient rows for {symbol}: {len(df)}")
            return TechnicalSignals(symbol=symbol)

        df = df.copy()
        signals = TechnicalSignals(symbol=symbol)

        try:
            self._add_indicators(df)
            self._extract_latest(df, signals)
            self._compute_probabilities(df, signals)
            self._classify_signal(signals)
        except Exception as e:
            logger.error(f"[TechEngine] Error computing signals for {symbol}: {e}", exc_info=True)

        return signals

    # ── Indicator computation ─────────────────────────────────────────────────

    def _add_indicators(self, df: pd.DataFrame) -> None:
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # RSI
        df["rsi_14"] = ta.momentum.RSIIndicator(close, window=14).rsi()
        df["rsi_7"] = ta.momentum.RSIIndicator(close, window=7).rsi()

        # MACD
        macd_ind = ta.trend.MACD(close, window_fast=12, window_slow=26, window_sign=9)
        df["macd_line"] = macd_ind.macd()
        df["macd_signal"] = macd_ind.macd_signal()
        df["macd_hist"] = macd_ind.macd_diff()

        # Bollinger Bands (20, 2)
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_pct"] = bb.bollinger_pband()
        df["bb_width"] = bb.bollinger_wband()

        # Moving averages
        df["ma_20"] = ta.trend.SMAIndicator(close, window=20).sma_indicator()
        df["ma_50"] = ta.trend.SMAIndicator(close, window=50).sma_indicator()
        df["ma_200"] = ta.trend.SMAIndicator(close, window=200).sma_indicator()
        df["ema_20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()

        # ATR
        df["atr_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

        # ADX
        adx = ta.trend.ADXIndicator(high, low, close, window=14)
        df["adx_14"] = adx.adx()
        df["adx_pos"] = adx.adx_pos()
        df["adx_neg"] = adx.adx_neg()

        # Volume indicators
        if "volume" in df.columns and df["volume"].sum() > 0:
            df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, df["volume"]).on_balance_volume()
            df["vwap_proxy"] = (df["high"] + df["low"] + close) / 3  # Typical price proxy

    def _extract_latest(self, df: pd.DataFrame, s: TechnicalSignals) -> None:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        s.rsi_14 = self._safe(last, "rsi_14", 50.0)
        s.rsi_7 = self._safe(last, "rsi_7", 50.0)

        s.macd_line = self._safe(last, "macd_line", 0.0)
        s.macd_signal = self._safe(last, "macd_signal", 0.0)
        s.macd_hist = self._safe(last, "macd_hist", 0.0)

        # MACD crossover detection
        prev_hist = self._safe(prev, "macd_hist", 0.0)
        if prev_hist < 0 and s.macd_hist > 0:
            s.macd_crossover = "bullish"
        elif prev_hist > 0 and s.macd_hist < 0:
            s.macd_crossover = "bearish"

        s.bb_upper = self._safe(last, "bb_upper", 0.0)
        s.bb_lower = self._safe(last, "bb_lower", 0.0)
        s.bb_middle = self._safe(last, "bb_middle", 0.0)
        s.bb_pct = self._safe(last, "bb_pct", 0.5)
        s.bb_width = self._safe(last, "bb_width", 0.0)

        s.ma_20 = self._safe(last, "ma_20", 0.0)
        s.ma_50 = self._safe(last, "ma_50", 0.0)
        s.ma_200 = self._safe(last, "ma_200", 0.0)

        # Golden/Death cross detection
        prev_ma20 = self._safe(prev, "ma_20", 0.0)
        prev_ma50 = self._safe(prev, "ma_50", 0.0)
        if prev_ma20 <= prev_ma50 and s.ma_20 > s.ma_50 and s.ma_50 > 0:
            s.ma_cross = "golden"
        elif prev_ma20 >= prev_ma50 and s.ma_20 < s.ma_50 and s.ma_50 > 0:
            s.ma_cross = "death"

        s.atr_14 = self._safe(last, "atr_14", 0.0)
        s.adx_14 = self._safe(last, "adx_14", 0.0)

    def _compute_probabilities(self, df: pd.DataFrame, s: TechnicalSignals) -> None:
        """
        Build probabilistic signals from indicator readings.
        Each indicator votes (+1 bullish, -1 bearish, 0 neutral) with a weight.
        Final probability uses a sigmoid transform on the weighted vote sum.
        """
        votes: list[tuple[float, float]] = []  # (vote, weight)

        # RSI: <30 oversold (bullish), >70 overbought (bearish)
        rsi_vote = self._rsi_vote(s.rsi_14)
        votes.append((rsi_vote, 0.20))

        # MACD: histogram direction + crossover
        macd_vote = np.sign(s.macd_hist)
        if s.macd_crossover == "bullish":
            macd_vote = 1.0
        elif s.macd_crossover == "bearish":
            macd_vote = -1.0
        votes.append((macd_vote, 0.25))

        # Bollinger Band position
        bb_vote = self._bb_vote(s.bb_pct, s.bb_width)
        votes.append((bb_vote, 0.15))

        # Moving average alignment
        ma_vote = self._ma_vote(s)
        votes.append((ma_vote, 0.20))

        # ADX trend strength
        s.trend_strength = float(np.clip(s.adx_14 / 50, 0, 1))
        trend_vote = np.sign(s.adx_14 - 25) if s.adx_14 > 20 else 0
        votes.append((trend_vote, 0.10))

        # Breakout detection: price near upper BB + rising volume
        s.breakout_prob = self._breakout_probability(df)
        s.reversal_prob = self._reversal_probability(df, s)

        # Weighted vote sum
        total_weight = sum(w for _, w in votes)
        weighted_sum = sum(v * w for v, w in votes) / total_weight

        # Sigmoid to get probability
        bull_prob = float(1 / (1 + np.exp(-weighted_sum * 3)))
        s.bullish_prob = round(bull_prob, 3)
        s.bearish_prob = round(1 - bull_prob, 3)

    def _classify_signal(self, s: TechnicalSignals) -> None:
        """Map probability to a human-readable signal with confidence."""
        bp = s.bullish_prob
        s.confidence = abs(bp - 0.5) * 2  # 0 at 50/50, 1 at extreme

        if bp >= 0.80:
            s.signal = "STRONG_BUY"
        elif bp >= 0.65:
            s.signal = "BUY"
        elif bp <= 0.20:
            s.signal = "STRONG_SELL"
        elif bp <= 0.35:
            s.signal = "SELL"
        else:
            s.signal = "NEUTRAL"

    # ── Signal helpers ────────────────────────────────────────────────────────

    def _rsi_vote(self, rsi: float) -> float:
        if rsi < 30:
            return 1.0 - (rsi / 30)   # Stronger the lower
        if rsi > 70:
            return -(rsi - 70) / 30   # Stronger the higher
        if rsi < 45:
            return 0.3
        if rsi > 55:
            return -0.3
        return 0.0

    def _bb_vote(self, bb_pct: float, bb_width: float) -> float:
        """
        Mean-reversion vote based on Bollinger Band position.
        Near lower band → bullish, near upper → bearish.
        If bandwidth is very narrow (squeeze), signal is unreliable.
        """
        if bb_width < 0.02:  # Squeeze — low confidence
            return 0.0
        if bb_pct < 0.1:
            return 0.8
        if bb_pct > 0.9:
            return -0.8
        return (0.5 - bb_pct) * 1.5  # Linear gradient

    def _ma_vote(self, s: TechnicalSignals) -> float:
        """Price position relative to moving averages."""
        if s.ma_200 == 0:
            return 0.0
        votes = []
        close_proxy = s.bb_middle  # Use BB middle (= MA20) as proxy for close
        if close_proxy > 0:
            if s.ma_20 > s.ma_50:
                votes.append(0.5)
            if s.ma_50 > s.ma_200:
                votes.append(0.5)
            if close_proxy > s.ma_200:
                votes.append(0.5)
        if s.ma_cross == "golden":
            return 1.0
        if s.ma_cross == "death":
            return -1.0
        if not votes:
            return 0.0
        return float(np.clip(sum(votes) / len(votes), -1, 1))

    def _breakout_probability(self, df: pd.DataFrame) -> float:
        """
        Estimate breakout probability:
        - Price near multi-week high
        - BB squeeze followed by expansion
        - Volume surge
        """
        if len(df) < 20:
            return 0.0
        recent = df.tail(20)
        last = df.iloc[-1]

        # Price at 20-day high?
        at_high = last["close"] >= recent["close"].quantile(0.90)

        # BB squeeze releasing (bb_width expanding)
        bb_now = self._safe(df.iloc[-1], "bb_width", 0)
        bb_5d_ago = self._safe(df.iloc[-5] if len(df) >= 5 else df.iloc[0], "bb_width", 0)
        squeeze_release = bb_now > bb_5d_ago * 1.3

        # Volume surge
        vol_surge = False
        if "volume" in df.columns and df["volume"].sum() > 0:
            avg_vol = df["volume"].tail(20).mean()
            vol_surge = last.get("volume", 0) > avg_vol * 1.5

        score = sum([at_high, squeeze_release, vol_surge]) / 3
        return float(score)

    def _reversal_probability(self, df: pd.DataFrame, s: TechnicalSignals) -> float:
        """
        Detect potential reversal:
        - RSI extreme divergence
        - MACD crossover at extreme
        - Price far from MA200
        """
        if len(df) < 30:
            return 0.0

        rsi_extreme = s.rsi_14 < 25 or s.rsi_14 > 75
        macd_cross = s.macd_crossover in ("bullish", "bearish")

        far_from_ma = False
        if s.ma_200 > 0:
            deviation = abs(s.bb_middle - s.ma_200) / s.ma_200
            far_from_ma = deviation > 0.15

        score = sum([rsi_extreme, macd_cross, far_from_ma]) / 3
        return float(score)

    @staticmethod
    def _safe(row, col: str, default: float) -> float:
        val = row.get(col, default) if hasattr(row, "get") else getattr(row, col, default)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
