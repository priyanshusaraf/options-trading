"""You cannot reach the order-placing broker by accident: it needs BOTH live flags
AND the live Kite provider. Default and mock always give the paper broker."""
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.broker_factory import live_execution_enabled, make_broker
from app.providers.mock import MockProvider


def test_paper_broker_by_default(monkeypatch):
    monkeypatch.delenv("PT_EXECUTION", raising=False)
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    init_db(reset=True)
    assert live_execution_enabled() is False
    assert isinstance(make_broker(MockProvider()), PaperBroker)


def test_both_flags_required(monkeypatch):
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    assert live_execution_enabled() is False          # ack flag missing
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    assert live_execution_enabled() is True


def test_live_flags_but_mock_provider_stays_paper(monkeypatch):
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    # even with both flags, the mock provider can never place a real order
    assert isinstance(make_broker(MockProvider()), PaperBroker)
