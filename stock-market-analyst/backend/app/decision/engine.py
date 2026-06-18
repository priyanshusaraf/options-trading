"""
Decision Engine — combines all analytical signals into ranked opportunities.

Signal sources (weighted):
  1. Quant score         (30%)
  2. Technical signals   (25%)
  3. News sentiment      (20%) — FinBERT or lexicon
  4. Event risk          (15%) — reduces conviction near high-impact events
  5. Options signals     (10%) — smart money positioning
  6. Regime adjustment   (applied as multiplier, not additive weight)

Outputs per symbol:
  - Overall score (–1 to +1)
  - Action: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
  - Confidence (0–1)
  - Reasoning breakdown (human-readable)
  - Suggested position size (as % of portfolio)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from backend.app.analytics.quant.engine import QuantMetrics
from backend.app.analytics.technical.engine import TechnicalSignals
from backend.app.analytics.options.engine import OptionsChainResult
from backend.app.intelligence.regime.detector import RegimeResult, Regime
from backend.app.intelligence.news.analyzer import NewsAnalysis
from backend.app.core.logging import logger


@dataclass
class Opportunity:
    symbol: str
    score: float                # –1 (strong sell) to +1 (strong buy)
    action: str                 # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    confidence: float           # 0–1
    suggested_weight: float     # Suggested portfolio weight (%)

    # Score components (for transparency)
    quant_score: float = 0.0
    technical_score: float = 0.0
    sentiment_score: float = 0.0
    event_risk_discount: float = 1.0
    regime_multiplier: float = 1.0

    # Reasoning
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics_summary: dict = field(default_factory=dict)


class DecisionEngine:
    """
    Combines all sub-engine outputs into ranked Opportunity objects.
    """

    # Signal weights (active components are normalized at runtime)
    WEIGHTS = {
        "quant": 0.30,
        "technical": 0.25,
        "sentiment": 0.20,
        "event_risk": 0.15,
        "options": 0.10,
    }

    def evaluate(
        self,
        symbol: str,
        quant: Optional[QuantMetrics] = None,
        technical: Optional[TechnicalSignals] = None,
        regime: Optional[RegimeResult] = None,
        news: Optional[NewsAnalysis] = None,
        options: Optional[OptionsChainResult] = None,
        sentiment_score: float = 0.0,      # –1 to +1 (from NLP module, overrides news if set)
        event_risk_level: str = "low",      # low / medium / high
    ) -> Opportunity:
        """
        Produce a single Opportunity for a symbol.
        """
        opp = Opportunity(symbol=symbol, score=0.0, action="HOLD", confidence=0.0, suggested_weight=0.0)

        reasons = []
        warnings = []
        active_weights = {}
        score_components = {}

        # ── Quant component ───────────────────────────────────────────────────
        if quant is not None:
            qs = float(quant.composite_score)
            opp.quant_score = qs
            score_components["quant"] = qs
            active_weights["quant"] = self.WEIGHTS["quant"]
            self._quant_reasons(quant, reasons, warnings)
        else:
            score_components["quant"] = 0.0

        # ── Technical component ───────────────────────────────────────────────
        if technical is not None:
            ts = float(technical.bullish_prob * 2 - 1)  # Convert 0-1 → -1 to +1
            opp.technical_score = ts
            score_components["technical"] = ts
            active_weights["technical"] = self.WEIGHTS["technical"]
            self._technical_reasons(technical, reasons, warnings)
        else:
            score_components["technical"] = 0.0

        # ── Sentiment component — use NewsAnalysis if available ───────────────
        effective_sentiment = sentiment_score
        if news is not None and news.article_count > 0:
            effective_sentiment = float(news.sentiment_score)
            if news.high_impact_events:
                reasons.append(f"High-impact news event detected: {news.high_impact_events[0][:80]}")
        opp.sentiment_score = effective_sentiment
        score_components["sentiment"] = effective_sentiment
        active_weights["sentiment"] = self.WEIGHTS["sentiment"]

        # ── Options component — smart money signal ────────────────────────────
        if options is not None and options.smart_money_signal != "NEUTRAL":
            opts_score = 0.5 if options.smart_money_signal == "BULLISH" else -0.5
            score_components["options"] = opts_score
            active_weights["options"] = self.WEIGHTS.get("options", 0.10)
            reasons += options.signal_reasons[:2]
            if options.vol_breakout_prob > 0.6:
                reasons.append(f"Elevated IV — vol breakout probability {options.vol_breakout_prob:.0%}.")

        # ── Event risk discount ───────────────────────────────────────────────
        event_discount = {"low": 1.0, "medium": 0.80, "high": 0.55}.get(event_risk_level, 1.0)
        opp.event_risk_discount = event_discount
        if event_risk_level == "high":
            warnings.append("High-impact event upcoming — conviction reduced 45%.")
        elif event_risk_level == "medium":
            warnings.append("Moderate event risk — conviction reduced 20%.")

        # ── Normalize weights ─────────────────────────────────────────────────
        total_w = sum(active_weights.values()) or 1.0
        norm_weights = {k: v / total_w for k, v in active_weights.items()}

        # ── Raw score ─────────────────────────────────────────────────────────
        raw_score = sum(score_components.get(k, 0.0) * w for k, w in norm_weights.items())

        # ── Regime adjustment ─────────────────────────────────────────────────
        regime_mult = 1.0
        if regime is not None:
            if raw_score > 0:
                regime_mult = regime.momentum_weight_adj if regime.is_trending else regime.mean_reversion_weight_adj
            else:
                regime_mult = 0.8  # Dampen sell signals in uncertain regimes
            opp.regime_multiplier = regime_mult
            reasons.append(f"Regime: {regime.regime.value} (confidence {regime.confidence:.0%})")

        adjusted_score = float(np.clip(raw_score * regime_mult * event_discount, -1, 1))
        opp.score = round(adjusted_score, 3)

        # ── Confidence ────────────────────────────────────────────────────────
        signal_agreement = self._signal_agreement(score_components)
        base_confidence = abs(adjusted_score) * signal_agreement
        opp.confidence = round(float(np.clip(base_confidence, 0, 1)), 3)

        # ── Action classification ─────────────────────────────────────────────
        opp.action = self._classify_action(adjusted_score, opp.confidence)

        # ── Position sizing (Kelly-inspired, conservative) ────────────────────
        if quant is not None:
            opp.suggested_weight = self._position_size(
                adjusted_score, opp.confidence, quant.annualized_vol, regime
            )

        opp.reasons = reasons
        opp.warnings = warnings
        opp.metrics_summary = self._build_summary(quant, technical, regime)

        return opp

    def rank(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Sort opportunities: highest score first, sell/hold last."""
        buy_ops = sorted(
            [o for o in opportunities if o.score > 0.1],
            key=lambda x: (x.score * x.confidence),
            reverse=True,
        )
        hold_ops = [o for o in opportunities if -0.1 <= o.score <= 0.1]
        sell_ops = sorted(
            [o for o in opportunities if o.score < -0.1],
            key=lambda x: (x.score * x.confidence),
        )
        return buy_ops + hold_ops + sell_ops

    # ── Private helpers ───────────────────────────────────────────────────────

    def _classify_action(self, score: float, confidence: float) -> str:
        if score >= 0.6 and confidence >= 0.6:
            return "STRONG_BUY"
        if score >= 0.25:
            return "BUY"
        if score <= -0.6 and confidence >= 0.6:
            return "STRONG_SELL"
        if score <= -0.25:
            return "SELL"
        return "HOLD"

    def _signal_agreement(self, components: dict[str, float]) -> float:
        """
        Measure how much the signals agree with each other.
        All pointing same direction → 1.0, mixed → 0.3.
        """
        values = [v for v in components.values() if v != 0]
        if not values:
            return 0.5
        signs = [np.sign(v) for v in values]
        unique = set(signs)
        if len(unique) == 1:
            return 1.0
        pos = signs.count(1)
        neg = signs.count(-1)
        total = pos + neg
        return float(max(pos, neg) / total) if total > 0 else 0.5

    def _position_size(
        self,
        score: float,
        confidence: float,
        ann_vol: float,
        regime: Optional[RegimeResult],
    ) -> float:
        """
        Conservative Kelly fraction:
        position = (conviction * regime_risk_discount) / (vol_normalized)
        Caps at 10% of portfolio for any single position.
        """
        if ann_vol <= 0 or score <= 0:
            return 0.0

        regime_discount = regime.vol_risk_discount if regime else 1.0
        vol_adj = min(ann_vol / 0.20, 3.0)  # Normalize: 20% vol = 1.0x
        raw_size = (score * confidence * regime_discount) / vol_adj * 0.15  # Max 15% base
        return round(float(np.clip(raw_size, 0, 0.10)) * 100, 1)  # Return as %

    def _quant_reasons(self, q: QuantMetrics, reasons: list, warnings: list) -> None:
        if q.composite_score > 0.3:
            reasons.append(f"Quant score is positive ({q.composite_score:.2f}): strong factor alignment.")
        if q.momentum_score > 0.4:
            reasons.append(f"Strong price momentum (score: {q.momentum_score:.2f}).")
        if q.sharpe_ratio > 1.5:
            reasons.append(f"Excellent Sharpe ratio ({q.sharpe_ratio:.2f}).")
        if q.max_drawdown < -0.30:
            warnings.append(f"Large historical drawdown: {q.max_drawdown:.1%}. Risk of deep corrections.")
        if q.var_95_hist < -0.03:
            warnings.append(f"Daily VaR (95%) is {q.var_95_hist:.2%} — significant tail risk.")
        if q.beta > 1.5:
            warnings.append(f"High beta ({q.beta:.2f}) — amplified market moves.")

    def _technical_reasons(self, t: TechnicalSignals, reasons: list, warnings: list) -> None:
        if t.rsi_14 < 35:
            reasons.append(f"RSI oversold ({t.rsi_14:.1f}) — potential bounce zone.")
        elif t.rsi_14 > 70:
            warnings.append(f"RSI overbought ({t.rsi_14:.1f}) — watch for profit taking.")
        if t.macd_crossover == "bullish":
            reasons.append("MACD bullish crossover detected — momentum turning positive.")
        elif t.macd_crossover == "bearish":
            warnings.append("MACD bearish crossover — momentum deteriorating.")
        if t.ma_cross == "golden":
            reasons.append("Golden cross (MA20 > MA50) — medium-term trend turning bullish.")
        elif t.ma_cross == "death":
            warnings.append("Death cross (MA20 < MA50) — medium-term trend bearish.")
        if t.breakout_prob > 0.6:
            reasons.append(f"Breakout probability is high ({t.breakout_prob:.0%}).")
        if t.trend_strength > 0.7:
            reasons.append(f"ADX indicates strong trend (strength: {t.trend_strength:.0%}).")

    def _build_summary(
        self,
        quant: Optional[QuantMetrics],
        technical: Optional[TechnicalSignals],
        regime: Optional[RegimeResult],
    ) -> dict:
        summary = {}
        if quant:
            summary["quant"] = {
                "composite_score": quant.composite_score,
                "beta": quant.beta,
                "sharpe": quant.sharpe_ratio,
                "var_95": quant.var_95_hist,
                "max_drawdown": quant.max_drawdown,
                "annualized_vol": quant.annualized_vol,
            }
        if technical:
            summary["technical"] = {
                "signal": technical.signal,
                "bullish_prob": technical.bullish_prob,
                "rsi_14": technical.rsi_14,
                "macd_crossover": technical.macd_crossover,
                "bb_pct": technical.bb_pct,
                "trend_strength": technical.trend_strength,
            }
        if regime:
            summary["regime"] = {
                "regime": regime.regime.value,
                "vol_regime": regime.vol_regime,
                "trend_strength": regime.trend_strength,
                "hurst": regime.is_trending,
            }
        return summary
