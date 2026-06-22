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


def test_make_broker_uses_a_bounded_configurable_order_timeout(monkeypatch):
    """L5: the live order poll timeout must be configurable AND bounded well under
    the old 30s, so a stuck poll can't hold the engine lock for half a minute."""
    import types
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    init_db(reset=True)
    prov = MockProvider()
    prov.name = "kite"            # look like the live provider
    prov.access_token = "tok"
    monkeypatch.setattr("app.providers.live_kite.LiveExecutionKite",
                        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None))
    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient",
                        lambda *a, **k: object())
    captured = {}

    def fake_lb(provider, client, *, poll_seconds=0.5, timeout_seconds=30.0, notifier=None):
        captured["poll"], captured["timeout"] = poll_seconds, timeout_seconds
        return "LB"

    monkeypatch.setattr("app.engine.live_broker.LiveBroker", fake_lb)
    assert make_broker(prov) == "LB"
    from app.core.config import get_settings
    s = get_settings()
    assert captured["timeout"] == s.order_timeout_seconds
    assert captured["poll"] == s.order_poll_seconds
    assert captured["timeout"] <= 15.0


def test_live_gate_reads_dotenv_via_settings(monkeypatch):
    """The flags must work from .env (Settings), not only a shell export — so the
    owner controls live mode from one file with no per-session exports. Simulate the
    .env-backed Settings with NO matching OS env var present."""
    from app.core.config import get_settings
    monkeypatch.delenv("PT_EXECUTION", raising=False)
    monkeypatch.delenv("PT_LIVE_ACK", raising=False)
    s = get_settings()
    monkeypatch.setattr(s, "execution", "live")
    monkeypatch.setattr(s, "live_ack", "I_UNDERSTAND_REAL_MONEY")
    assert live_execution_enabled() is True
    monkeypatch.setattr(s, "live_ack", "wrong")     # ack must match exactly
    assert live_execution_enabled() is False
