"""
Tests for the Alerts Engine.
Uses in-memory SQLite for isolation from real data.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from backend.app.intelligence.alerts.engine import AlertsEngine, AlertRequest, AlertType


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """AlertsEngine backed by in-memory SQLite for test isolation."""
    import sqlalchemy
    from sqlalchemy.orm import sessionmaker
    from backend.app.data.models.database import Base

    test_engine = sqlalchemy.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)

    ae = AlertsEngine()
    ae.Session = sessionmaker(bind=test_engine)
    return ae


# ── CRUD Tests ────────────────────────────────────────────────────────────────

class TestAlertCRUD:
    def test_create_alert(self, engine):
        req = AlertRequest(
            symbol="RELIANCE",
            alert_type=AlertType.PRICE_ABOVE,
            threshold=2500.0,
        )
        alert = engine.create(req)
        assert alert.id is not None
        assert alert.symbol == "RELIANCE"
        assert alert.threshold == 2500.0
        assert alert.triggered is False

    def test_list_alerts_empty(self, engine):
        alerts = engine.list_alerts()
        assert alerts == []

    def test_list_alerts_with_data(self, engine):
        for i in range(3):
            engine.create(AlertRequest("STOCK", AlertType.PRICE_ABOVE, float(100 + i * 10)))
        alerts = engine.list_alerts()
        assert len(alerts) == 3

    def test_list_alerts_filter_by_symbol(self, engine):
        engine.create(AlertRequest("RELIANCE", AlertType.PRICE_ABOVE, 2500.0))
        engine.create(AlertRequest("TCS", AlertType.PRICE_ABOVE, 3500.0))
        reliance_alerts = engine.list_alerts(symbol="RELIANCE")
        assert all(a.symbol == "RELIANCE" for a in reliance_alerts)
        assert len(reliance_alerts) == 1

    def test_list_alerts_filter_triggered(self, engine):
        engine.create(AlertRequest("RELIANCE", AlertType.PRICE_ABOVE, 2500.0))
        pending = engine.list_alerts(triggered=False)
        triggered = engine.list_alerts(triggered=True)
        assert len(pending) == 1
        assert len(triggered) == 0

    def test_get_alert(self, engine):
        created = engine.create(AlertRequest("RELIANCE", AlertType.RSI_OVERSOLD, 30.0))
        fetched = engine.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_nonexistent_returns_none(self, engine):
        result = engine.get(99999)
        assert result is None

    def test_delete_alert(self, engine):
        created = engine.create(AlertRequest("RELIANCE", AlertType.PRICE_ABOVE, 2500.0))
        deleted = engine.delete(created.id)
        assert deleted is True
        assert engine.get(created.id) is None

    def test_delete_nonexistent_returns_false(self, engine):
        assert engine.delete(99999) is False

    def test_reset_alert(self, engine):
        created = engine.create(AlertRequest("RELIANCE", AlertType.PRICE_ABOVE, 2500.0))

        # Manually trigger it
        with engine.Session() as session:
            from backend.app.data.models.database import Alert
            alert = session.query(Alert).get(created.id)
            alert.triggered = True
            alert.triggered_at = datetime.utcnow()
            session.commit()

        reset = engine.reset(created.id)
        assert reset.triggered is False
        assert reset.triggered_at is None

    def test_default_condition_generated(self, engine):
        req = AlertRequest("TCS", AlertType.RSI_OVERSOLD, 30.0)
        alert = engine.create(req)
        assert "RSI" in alert.condition or "oversold" in alert.condition.lower()


# ── Alert Condition Checks ────────────────────────────────────────────────────

class TestAlertConditionEvaluation:
    def _make_quant(self, composite=0.5, drawdown=-0.1):
        q = MagicMock()
        q.composite_score = composite
        q.max_drawdown = drawdown
        return q

    def _make_tech(self, rsi=50, breakout=0.3, reversal=0.2, macd_hist=0.01):
        t = MagicMock()
        t.rsi_14 = rsi
        t.breakout_prob = breakout
        t.reversal_prob = reversal
        t.macd_hist = macd_hist
        return t

    def _make_alert(self, alert_type: str, threshold: float):
        a = MagicMock()
        a.alert_type = alert_type
        a.threshold = threshold
        return a

    def test_price_above_triggered(self, engine):
        alert = self._make_alert("price_above", 2400.0)
        assert engine._check(alert, None, None, price=2500.0) is True

    def test_price_above_not_triggered(self, engine):
        alert = self._make_alert("price_above", 2600.0)
        assert engine._check(alert, None, None, price=2500.0) is False

    def test_price_below_triggered(self, engine):
        alert = self._make_alert("price_below", 2600.0)
        assert engine._check(alert, None, None, price=2500.0) is True

    def test_rsi_oversold_triggered(self, engine):
        alert = self._make_alert("rsi_oversold", 30.0)
        tech = self._make_tech(rsi=25)
        assert engine._check(alert, None, tech, price=None) is True

    def test_rsi_overbought_triggered(self, engine):
        alert = self._make_alert("rsi_overbought", 70.0)
        tech = self._make_tech(rsi=75)
        assert engine._check(alert, None, tech, price=None) is True

    def test_breakout_triggered(self, engine):
        alert = self._make_alert("breakout", 0.7)
        tech = self._make_tech(breakout=0.8)
        assert engine._check(alert, None, tech, price=None) is True

    def test_quant_score_triggered(self, engine):
        alert = self._make_alert("quant_score", 0.4)
        quant = self._make_quant(composite=0.6)
        assert engine._check(alert, quant, None, price=None) is True

    def test_quant_score_below_triggered(self, engine):
        alert = self._make_alert("quant_score_below", 0.2)
        quant = self._make_quant(composite=0.1)
        assert engine._check(alert, quant, None, price=None) is True

    def test_macd_bullish_triggered(self, engine):
        alert = self._make_alert("macd_bullish_cross", 0.0)
        tech = self._make_tech(macd_hist=0.5)
        assert engine._check(alert, None, tech, price=None) is True

    def test_macd_bearish_triggered(self, engine):
        alert = self._make_alert("macd_bearish_cross", 0.0)
        tech = self._make_tech(macd_hist=-0.5)
        assert engine._check(alert, None, tech, price=None) is True

    def test_max_drawdown_triggered(self, engine):
        alert = self._make_alert("max_drawdown", -0.20)
        quant = self._make_quant(drawdown=-0.30)
        assert engine._check(alert, quant, None, price=None) is True

    def test_no_data_returns_false(self, engine):
        alert = self._make_alert("rsi_oversold", 30.0)
        assert engine._check(alert, None, None, price=None) is False
