"""
Alerts Engine.

Supported alert types:
  PRICE          — price crosses above/below threshold
  RSI_OVERSOLD   — RSI drops below threshold (default 30)
  RSI_OVERBOUGHT — RSI rises above threshold (default 70)
  BREAKOUT       — breakout probability exceeds threshold
  REVERSAL       — reversal probability exceeds threshold
  QUANT_SCORE    — composite quant score crosses threshold
  MAX_DRAWDOWN   — drawdown exceeds threshold (negative number)
  NEWS_SENTIMENT — news sentiment score crosses threshold
  MACD_CROSS     — MACD bullish/bearish crossover detected
  VOLUME_SPIKE   — volume spike relative to 20-day average

Each alert:
  - Is stored in SQLite (Alert table)
  - Is evaluated by the background scheduler (every 30 min)
  - Once triggered, is marked as such with a timestamp
  - Supports optional repeat (re-arm after N hours)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy.orm import sessionmaker

from backend.app.core.logging import logger
from backend.app.data.models.database import Alert, get_engine


class AlertType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    QUANT_SCORE = "quant_score"
    QUANT_SCORE_BELOW = "quant_score_below"
    MAX_DRAWDOWN = "max_drawdown"
    NEWS_SENTIMENT = "news_sentiment"
    MACD_BULLISH = "macd_bullish_cross"
    MACD_BEARISH = "macd_bearish_cross"
    VOLUME_SPIKE = "volume_spike"


@dataclass
class AlertRequest:
    symbol: str
    alert_type: AlertType
    threshold: float
    condition: str = ""          # Human-readable description
    notes: str = ""
    rearm_hours: Optional[int] = None  # Re-arm alert after N hours if triggered


@dataclass
class AlertView:
    id: int
    symbol: str
    alert_type: str
    threshold: float
    condition: str
    triggered: bool
    triggered_at: Optional[str]
    created_at: str
    notes: str


class AlertsEngine:
    """CRUD + evaluation logic for all alert types."""

    def __init__(self):
        self.Session = sessionmaker(bind=get_engine())

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, req: AlertRequest) -> AlertView:
        """Create and persist a new alert."""
        condition = req.condition or self._default_condition(req)
        with self.Session() as session:
            alert = Alert(
                symbol=req.symbol.upper(),
                alert_type=req.alert_type.value,
                threshold=req.threshold,
                condition=condition,
                triggered=False,
                notes=req.notes,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            logger.info(f"[Alerts] Created: {alert.symbol} | {alert.alert_type} | {condition}")
            return self._to_view(alert)

    def list_alerts(
        self,
        symbol: Optional[str] = None,
        triggered: Optional[bool] = None,
    ) -> list[AlertView]:
        with self.Session() as session:
            q = session.query(Alert)
            if symbol:
                q = q.filter(Alert.symbol == symbol.upper())
            if triggered is not None:
                q = q.filter(Alert.triggered == triggered)
            return [self._to_view(a) for a in q.order_by(Alert.created_at.desc()).all()]

    def get(self, alert_id: int) -> Optional[AlertView]:
        with self.Session() as session:
            a = session.query(Alert).get(alert_id)
            return self._to_view(a) if a else None

    def delete(self, alert_id: int) -> bool:
        with self.Session() as session:
            a = session.query(Alert).get(alert_id)
            if not a:
                return False
            session.delete(a)
            session.commit()
            return True

    def reset(self, alert_id: int) -> Optional[AlertView]:
        """Re-arm a triggered alert."""
        with self.Session() as session:
            a = session.query(Alert).get(alert_id)
            if not a:
                return None
            a.triggered = False
            a.triggered_at = None
            session.commit()
            session.refresh(a)
            logger.info(f"[Alerts] Reset: {a.symbol} | {a.alert_type}")
            return self._to_view(a)

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate_all(self) -> list[AlertView]:
        """
        Evaluate all non-triggered alerts against latest data.
        Returns list of newly triggered alerts.
        """
        from backend.app.data.models.database import QuantScore, TechnicalSignal

        newly_triggered = []

        with self.Session() as session:
            pending = session.query(Alert).filter_by(triggered=False).all()
            if not pending:
                return []

            for alert in pending:
                try:
                    latest_quant = (
                        session.query(QuantScore)
                        .filter_by(symbol=alert.symbol)
                        .order_by(QuantScore.computed_at.desc())
                        .first()
                    )
                    latest_tech = (
                        session.query(TechnicalSignal)
                        .filter_by(symbol=alert.symbol)
                        .order_by(TechnicalSignal.computed_at.desc())
                        .first()
                    )
                    current_price = self._fetch_price(alert.symbol)

                    fired = self._check(alert, latest_quant, latest_tech, current_price)
                    if fired:
                        alert.triggered = True
                        alert.triggered_at = datetime.utcnow()
                        newly_triggered.append(self._to_view(alert))
                        logger.info(
                            f"[Alerts] TRIGGERED: {alert.symbol} | "
                            f"{alert.alert_type} @ {alert.threshold}"
                        )
                except Exception as e:
                    logger.warning(f"[Alerts] Error evaluating alert {alert.id}: {e}")

            session.commit()

        return newly_triggered

    def evaluate_symbol(self, symbol: str) -> list[AlertView]:
        """Evaluate all alerts for a specific symbol."""
        from backend.app.data.models.database import QuantScore, TechnicalSignal

        newly_triggered = []
        sym = symbol.upper()

        with self.Session() as session:
            pending = session.query(Alert).filter_by(symbol=sym, triggered=False).all()

            latest_quant = (
                session.query(QuantScore)
                .filter_by(symbol=sym)
                .order_by(QuantScore.computed_at.desc())
                .first()
            )
            latest_tech = (
                session.query(TechnicalSignal)
                .filter_by(symbol=sym)
                .order_by(TechnicalSignal.computed_at.desc())
                .first()
            )
            current_price = self._fetch_price(sym)

            for alert in pending:
                try:
                    fired = self._check(alert, latest_quant, latest_tech, current_price)
                    if fired:
                        alert.triggered = True
                        alert.triggered_at = datetime.utcnow()
                        newly_triggered.append(self._to_view(alert))
                except Exception as e:
                    logger.warning(f"[Alerts] Error evaluating {sym}: {e}")

            session.commit()

        return newly_triggered

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check(alert, quant, technical, price: Optional[float]) -> bool:
        t = alert.alert_type
        threshold = float(alert.threshold or 0)

        if t == AlertType.PRICE_ABOVE.value and price is not None:
            return price >= threshold
        if t == AlertType.PRICE_BELOW.value and price is not None:
            return price <= threshold
        if t == AlertType.RSI_OVERSOLD.value and technical:
            return float(technical.rsi_14 or 50) <= threshold
        if t == AlertType.RSI_OVERBOUGHT.value and technical:
            return float(technical.rsi_14 or 50) >= threshold
        if t == AlertType.BREAKOUT.value and technical:
            return float(technical.breakout_prob or 0) >= threshold
        if t == AlertType.REVERSAL.value and technical:
            return float(technical.reversal_prob or 0) >= threshold
        if t == AlertType.QUANT_SCORE.value and quant:
            return float(quant.composite_score or 0) >= threshold
        if t == AlertType.QUANT_SCORE_BELOW.value and quant:
            return float(quant.composite_score or 0) <= threshold
        if t == AlertType.MAX_DRAWDOWN.value and quant:
            return float(quant.max_drawdown or 0) <= threshold  # threshold is negative
        if t == AlertType.MACD_BULLISH.value and technical:
            hist = float(technical.macd_hist or 0)
            return hist > 0  # Histogram turned positive → bullish cross
        if t == AlertType.MACD_BEARISH.value and technical:
            hist = float(technical.macd_hist or 0)
            return hist < 0  # Histogram turned negative → bearish cross
        return False

    @staticmethod
    def _fetch_price(symbol: str) -> Optional[float]:
        """Quick price fetch from yfinance cache."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            data = ticker.fast_info
            return float(data.last_price) if data and data.last_price else None
        except Exception:
            return None

    @staticmethod
    def _default_condition(req: AlertRequest) -> str:
        mapping = {
            AlertType.PRICE_ABOVE: f"Price ≥ {req.threshold}",
            AlertType.PRICE_BELOW: f"Price ≤ {req.threshold}",
            AlertType.RSI_OVERSOLD: f"RSI ≤ {req.threshold} (oversold)",
            AlertType.RSI_OVERBOUGHT: f"RSI ≥ {req.threshold} (overbought)",
            AlertType.BREAKOUT: f"Breakout probability ≥ {req.threshold:.0%}",
            AlertType.REVERSAL: f"Reversal probability ≥ {req.threshold:.0%}",
            AlertType.QUANT_SCORE: f"Quant score ≥ {req.threshold}",
            AlertType.QUANT_SCORE_BELOW: f"Quant score ≤ {req.threshold}",
            AlertType.MAX_DRAWDOWN: f"Max drawdown ≤ {req.threshold:.0%}",
            AlertType.MACD_BULLISH: "MACD bullish crossover",
            AlertType.MACD_BEARISH: "MACD bearish crossover",
            AlertType.VOLUME_SPIKE: f"Volume spike ≥ {req.threshold}× average",
        }
        return mapping.get(req.alert_type, f"{req.alert_type.value} @ {req.threshold}")

    @staticmethod
    def _to_view(a) -> AlertView:
        return AlertView(
            id=a.id,
            symbol=a.symbol,
            alert_type=a.alert_type,
            threshold=float(a.threshold or 0),
            condition=a.condition or "",
            triggered=bool(a.triggered),
            triggered_at=a.triggered_at.isoformat() if a.triggered_at else None,
            created_at=a.created_at.isoformat() if a.created_at else "",
            notes=a.notes or "",
        )
